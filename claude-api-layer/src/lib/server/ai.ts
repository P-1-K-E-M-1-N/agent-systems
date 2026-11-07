/**
 * Server-side AI copywriting (PV backend §6 / PLAN.md §5).
 *
 * This is the real implementation behind the four AI seams the composer calls
 * (generate / refine / variations / custom-refine). It runs ONLY on the server
 * — the Anthropic key never reaches the browser. The API route handlers in
 * `src/app/api/ai/*` are thin wrappers around the functions here.
 *
 * Design notes:
 *  - Model: claude-opus-4-8 (the latest Claude; see CLAUDE_MODEL).
 *  - Structured output via tool use: we force a single tool call whose input
 *    schema IS the JSON shape the composer expects, so we never parse free text.
 *  - Prompt caching: the system prompt + platform-norms table are stable across
 *    every request and marked `cache_control: ephemeral`. Only the final user
 *    turn (the idea/tone/transcript) varies. Today these blocks are short enough
 *    that they may fall under the model's minimum cacheable size, but the
 *    breakpoints are correct for when per-workspace brand-voice examples are
 *    added (PLAN.md §5 block 3) and the prefix grows.
 *  - Fallback: if ANTHROPIC_API_KEY is unset we return deterministic placeholder
 *    copy (the old mock) so local dev still works. This is logged, never silent.
 */
import "server-only";

import Anthropic from "@anthropic-ai/sdk";

import {
  PLATFORMS,
  PLATFORM_ORDER,
  type ComposerDraft,
  type PlatformId,
} from "../platforms";
import type { RefineAction, Tone } from "../services";

/** The latest Claude model. See the claude-api skill's model table. */
const CLAUDE_MODEL = "claude-opus-4-8";

// ---------------------------------------------------------------------------
// Client (lazy + optional)
// ---------------------------------------------------------------------------

let cached: Anthropic | null | undefined;

/** Returns a client, or null when no key is configured (→ fallback path). */
function getClient(): Anthropic | null {
  if (cached !== undefined) return cached;
  const apiKey = process.env.ANTHROPIC_API_KEY;
  cached = apiKey ? new Anthropic({ apiKey }) : null;
  if (!cached) {
    console.warn(
      "[ai] ANTHROPIC_API_KEY is not set — returning deterministic placeholder copy. " +
        "Set it in .env.local to enable real AI generation.",
    );
  }
  return cached;
}

// ---------------------------------------------------------------------------
// Stable, cacheable prompt blocks
// ---------------------------------------------------------------------------

const SYSTEM_PROMPT = `You are an expert short-form video copywriter who writes platform-native captions, titles, and hashtags for YouTube Shorts, Instagram Reels, and TikTok.

Rules:
- Front-load the hook. The first line must earn the next second of attention.
- Write in the requested tone. Match the platform's native voice, not a press release.
- Respect each platform's character limits (given below). Never exceed them.
- Hashtags: return them WITHOUT the leading '#'. Lowercase unless a proper noun. No spaces.
- Do not invent facts about the video beyond the idea/transcript you are given.
- Always respond by calling the provided tool. Do not write any prose outside the tool call.`;

/** Per-platform constraints, derived from the single source of truth in platforms.ts. */
const PLATFORM_NORMS = [
  `YouTube Shorts — title ≤ ${PLATFORMS.youtube.primaryLimit} chars; description ≤ ${PLATFORMS.youtube.secondaryLimit} chars. Append #Shorts. 3–5 hashtags.`,
  `Instagram Reels — caption ≤ ${PLATFORMS.instagram.primaryLimit} chars, but only ~${PLATFORMS.instagram.foldAt} show before "… more", so put the hook first. 3–8 hashtags.`,
  `TikTok — caption punchy, hook in the first line; recommended ~${PLATFORMS.tiktok.recommend} chars. 3–6 trend-aware hashtags.`,
].join("\n");

/**
 * System blocks shared by every call. The last block carries the cache
 * breakpoint so tools + system are cached together (render order is
 * tools → system → messages).
 */
function systemBlocks(): Anthropic.TextBlockParam[] {
  return [
    { type: "text", text: SYSTEM_PROMPT },
    {
      type: "text",
      text: `Platform norms:\n${PLATFORM_NORMS}`,
      cache_control: { type: "ephemeral" },
    },
  ];
}

// ---------------------------------------------------------------------------
// Tool schemas (stable → kept identical across requests to preserve the cache)
// ---------------------------------------------------------------------------

const platformCopyObject = {
  youtube: {
    type: "object",
    description: "Only fill this if YouTube is a requested platform.",
    properties: {
      title: { type: "string", description: "Video title, ≤ 100 chars." },
      description: { type: "string", description: "Video description. End with #Shorts." },
      hashtags: { type: "array", items: { type: "string" }, description: "Tags without '#'." },
    },
  },
  instagram: {
    type: "object",
    description: "Only fill this if Instagram is a requested platform.",
    properties: {
      caption: { type: "string", description: "Reel caption, hook first, ≤ 2200 chars." },
      hashtags: { type: "array", items: { type: "string" } },
    },
  },
  tiktok: {
    type: "object",
    description: "Only fill this if TikTok is a requested platform.",
    properties: {
      caption: { type: "string", description: "TikTok caption, hook first." },
      hashtags: { type: "array", items: { type: "string" } },
    },
  },
} as const;

const COMPOSE_TOOL: Anthropic.Tool = {
  name: "compose_posts",
  description: "Return platform-native copy for each requested platform.",
  input_schema: {
    type: "object",
    properties: platformCopyObject as unknown as Record<string, unknown>,
  },
};

const REFINE_TOOL: Anthropic.Tool = {
  name: "return_refined",
  description: "Return the refined primary text and/or hashtags.",
  input_schema: {
    type: "object",
    properties: {
      primary: { type: "string", description: "The rewritten primary text, if the action edits text." },
      hashtags: { type: "array", items: { type: "string" }, description: "The new hashtag list (no '#'), if the action edits hashtags." },
    },
  },
};

const VARIATIONS_TOOL: Anthropic.Tool = {
  name: "return_variations",
  description: "Return exactly 3 alternative primary-text options.",
  input_schema: {
    type: "object",
    properties: {
      variations: {
        type: "array",
        items: { type: "string" },
        description: "Exactly 3 distinct alternative hooks/captions.",
      },
    },
    required: ["variations"],
  },
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function asString(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}

function asStringArray(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out = v.filter((x): x is string => typeof x === "string");
  return out.length ? out : undefined;
}

/** Pull the single forced tool_use input out of a response. */
function toolInput(msg: Anthropic.Message): Record<string, unknown> {
  for (const block of msg.content) {
    if (block.type === "tool_use") return block.input as Record<string, unknown>;
  }
  return {};
}

// ---------------------------------------------------------------------------
// generate
// ---------------------------------------------------------------------------

export interface GenerateInput {
  idea: string;
  platforms: PlatformId[];
  tone?: Tone;
  transcript?: string;
}

export async function generate(input: GenerateInput): Promise<Partial<ComposerDraft>> {
  const client = getClient();
  const platforms = input.platforms.filter((p) => PLATFORM_ORDER.includes(p));
  if (!client) return fallbackGenerate(input.idea, input.tone ?? "punchy", platforms);

  const tone = input.tone ?? "punchy";
  const task = [
    `Idea: ${input.idea.trim() || "(none — infer from transcript)"}`,
    `Tone: ${tone}`,
    `Platforms to write for: ${platforms.join(", ")}`,
    input.transcript ? `Transcript of the video:\n${input.transcript}` : "",
    "Fill ONLY the requested platforms in the tool call.",
  ]
    .filter(Boolean)
    .join("\n\n");

  const msg = await client.messages.create({
    model: CLAUDE_MODEL,
    max_tokens: 3072,
    thinking: { type: "disabled" },
    system: systemBlocks(),
    tools: [COMPOSE_TOOL],
    tool_choice: { type: "tool", name: COMPOSE_TOOL.name },
    messages: [{ role: "user", content: task }],
  });

  const out = toolInput(msg);
  const draft: Partial<ComposerDraft> = {};

  if (platforms.includes("youtube") && out.youtube && typeof out.youtube === "object") {
    const y = out.youtube as Record<string, unknown>;
    draft.youtube = {
      enabled: true,
      primary: (asString(y.title) ?? "").slice(0, PLATFORMS.youtube.primaryLimit),
      secondary: asString(y.description) ?? "",
      hashtags: asStringArray(y.hashtags) ?? [],
    };
  }
  if (platforms.includes("instagram") && out.instagram && typeof out.instagram === "object") {
    const i = out.instagram as Record<string, unknown>;
    draft.instagram = {
      enabled: true,
      primary: (asString(i.caption) ?? "").slice(0, PLATFORMS.instagram.primaryLimit),
      hashtags: asStringArray(i.hashtags) ?? [],
    };
  }
  if (platforms.includes("tiktok") && out.tiktok && typeof out.tiktok === "object") {
    const t = out.tiktok as Record<string, unknown>;
    draft.tiktok = {
      enabled: true,
      primary: (asString(t.caption) ?? "").slice(0, PLATFORMS.tiktok.primaryLimit),
      hashtags: asStringArray(t.hashtags) ?? [],
    };
  }

  return draft;
}

// ---------------------------------------------------------------------------
// refine
// ---------------------------------------------------------------------------

const REFINE_INSTRUCTIONS: Record<RefineAction, string> = {
  shorten: "Rewrite the text to be much shorter — one punchy line. Return only `primary`.",
  punchier: "Rewrite the text to be punchier and more scroll-stopping. Return only `primary`.",
  emoji: "Add tasteful, relevant emoji to the text without changing its meaning. Return only `primary`.",
  hashtags: "Suggest a better, fuller hashtag set (return the FULL list, not just additions) in `hashtags`. Do not change `primary`.",
};

export async function refine(
  action: RefineAction,
  text: string,
  hashtags: string[],
): Promise<{ primary?: string; hashtags?: string[] }> {
  const client = getClient();
  if (!client) return fallbackRefine(action, text, hashtags);

  const task = [
    REFINE_INSTRUCTIONS[action],
    `Current text:\n${text}`,
    `Current hashtags (no '#'): ${hashtags.join(", ") || "(none)"}`,
  ].join("\n\n");

  const msg = await client.messages.create({
    model: CLAUDE_MODEL,
    max_tokens: 1024,
    thinking: { type: "disabled" },
    system: systemBlocks(),
    tools: [REFINE_TOOL],
    tool_choice: { type: "tool", name: REFINE_TOOL.name },
    messages: [{ role: "user", content: task }],
  });

  const out = toolInput(msg);
  if (action === "hashtags") return { hashtags: asStringArray(out.hashtags) ?? hashtags };
  return { primary: asString(out.primary) ?? text };
}

// ---------------------------------------------------------------------------
// variations
// ---------------------------------------------------------------------------

export async function variations(idea: string, tone: Tone): Promise<string[]> {
  const client = getClient();
  if (!client) return fallbackVariations(idea, tone);

  const msg = await client.messages.create({
    model: CLAUDE_MODEL,
    max_tokens: 1024,
    thinking: { type: "disabled" },
    system: systemBlocks(),
    tools: [VARIATIONS_TOOL],
    tool_choice: { type: "tool", name: VARIATIONS_TOOL.name },
    messages: [
      {
        role: "user",
        content: `Give exactly 3 distinct ${tone} primary-text options for this idea: ${idea.trim() || "this clip"}`,
      },
    ],
  });

  return asStringArray(toolInput(msg).variations)?.slice(0, 3) ?? fallbackVariations(idea, tone);
}

// ---------------------------------------------------------------------------
// customRefine (free-text instruction → single rewritten string)
// ---------------------------------------------------------------------------

export async function customRefine(text: string, instruction: string): Promise<string> {
  const client = getClient();
  const ins = instruction.trim();
  if (!ins) return text;
  if (!client) return fallbackCustomRefine(text, ins);

  const msg = await client.messages.create({
    model: CLAUDE_MODEL,
    max_tokens: 1024,
    thinking: { type: "disabled" },
    system:
      "You edit short-form video copy. Apply the user's instruction and return ONLY the edited text — no preamble, no quotes, no explanation.",
    messages: [
      { role: "user", content: `Text:\n${text}\n\nInstruction: ${ins}` },
    ],
  });

  for (const block of msg.content) {
    if (block.type === "text" && block.text.trim()) return block.text.trim();
  }
  return text;
}

// ---------------------------------------------------------------------------
// Deterministic fallback (no API key) — mirrors the original mock so local dev
// and demos still work. Surfaced via the console.warn in getClient().
// ---------------------------------------------------------------------------

const HASHTAG_BANK = ["shorts", "reels", "fyp", "viral", "howto", "behindthescenes", "creator", "tutorial"];
const EXTRA_TAGS = ["viral", "trending", "creator", "mustwatch", "tips", "save"];

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function hook(idea: string, tone: Tone): string {
  const i = (idea.trim() || "this clip").replace(/\.$/, "");
  switch (tone) {
    case "friendly":
      return `Hey! A quick one on ${i} 😊`;
    case "professional":
      return `Here's a practical look at ${i}.`;
    case "playful":
      return `ok ${i}… but make it fun 🤪`;
    default:
      return `You won't believe what happened with ${i} 👀`;
  }
}

const YT_TITLE: Record<Tone, (idea: string) => string> = {
  punchy: (i) => `${capitalize(i)} — here's how`,
  friendly: (i) => `Let's talk ${i} (the easy way)`,
  professional: (i) => `${capitalize(i)}: a quick guide`,
  playful: (i) => `${capitalize(i)}?! watch this 👀`,
};

function fallbackGenerate(idea: string, tone: Tone, platforms: PlatformId[]): Partial<ComposerDraft> {
  const theIdea = idea.trim() || "my latest video";
  const tags = HASHTAG_BANK.slice(0, 5);
  const out: Partial<ComposerDraft> = {};
  for (const id of PLATFORM_ORDER) {
    if (!platforms.includes(id)) continue;
    if (id === "youtube") {
      out.youtube = {
        enabled: true,
        primary: YT_TITLE[tone](theIdea).slice(0, PLATFORMS.youtube.primaryLimit),
        secondary: `In this Short: ${theIdea}. Subscribe for more.\n\n#Shorts`,
        hashtags: ["Shorts", ...tags.slice(0, 3)],
      };
    } else if (id === "instagram") {
      out.instagram = {
        enabled: true,
        primary: `${hook(theIdea, tone)}\n\nHere's the full story 👇 Save this for later.`,
        hashtags: tags,
      };
    } else {
      out.tiktok = {
        enabled: true,
        primary: `${hook(theIdea, tone)} #fyp`,
        hashtags: ["fyp", ...tags.slice(0, 3)],
      };
    }
  }
  return out;
}

function fallbackRefine(
  action: RefineAction,
  text: string,
  hashtags: string[],
): { primary?: string; hashtags?: string[] } {
  if (action === "hashtags") {
    const have = new Set(hashtags);
    const add = EXTRA_TAGS.filter((t) => !have.has(t)).slice(0, 3);
    return { hashtags: [...hashtags, ...add] };
  }
  if (action === "shorten") {
    const firstLine = text.split("\n")[0];
    const sentence = firstLine.split(/[.!?]\s/)[0];
    return { primary: (sentence || firstLine).trim().slice(0, 90) };
  }
  if (action === "punchier") {
    const core = text.replace(/^[^a-zA-Z0-9]+/, "").split(/[.\n]/)[0].trim();
    return { primary: `Stop scrolling 🚫 ${core || "you need to see this"} 🔥` };
  }
  const sprinkled = text.replace(/\b(love|new|best|easy|fast|tip|tips)\b/gi, (m) => `${m} ✨`);
  return { primary: `${sprinkled} 🙌` };
}

function fallbackVariations(idea: string, tone: Tone): string[] {
  const i = (idea.trim() || "this clip").replace(/\.$/, "");
  return [
    hook(i, tone),
    `${capitalize(i)} in 30 seconds ⏱️ — save this for later`,
    `nobody's talking about ${i} like this 👇`,
  ];
}

function fallbackCustomRefine(text: string, instruction: string): string {
  const l = instruction.toLowerCase();
  if (l.includes("cta") || l.includes("call to action")) return `${text}\n\n👉 Follow for more.`;
  if (l.includes("question")) return `${text}\n\nWhat would you try first? 💬`;
  if (l.includes("hook")) return `Wait for it… ${text}`;
  if (l.includes("short")) return text.split(/[.!?]\s/)[0].trim();
  if (l.includes("emoji")) return `${text} 🔥✨`;
  return `${text}\n\n(${instruction})`;
}
