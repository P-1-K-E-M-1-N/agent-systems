# Claude API generation layer

The server-side copywriting layer from a short-form video publishing tool (Next.js App Router). The composer in the browser calls four routes; each is a thin wrapper around [`src/lib/server/ai.ts`](src/lib/server/ai.ts), which is where the real work happens.

| Route | Purpose |
|---|---|
| `POST /api/ai/generate` | Write captions, titles and hashtags from an idea, tone and optional transcript |
| `POST /api/ai/refine` | Apply a preset change (such as shorter or punchier) to existing copy |
| `POST /api/ai/custom-refine` | Apply a free-text instruction to existing copy |
| `POST /api/ai/variations` | Return alternative versions to choose from |

## Design choices

- **Structured output through forced tool use.** Every request forces one tool call whose input schema is the exact JSON shape the composer expects, so the code never parses free text.
- **Prompt caching.** The system prompt and the platform-norms table don't change between requests, so they're marked `cache_control: ephemeral`. Only the final user turn varies.
- **The key stays on the server.** `ai.ts` imports `server-only`, so the Anthropic key can't be bundled into browser code.
- **Visible fallback.** With no `ANTHROPIC_API_KEY`, the layer returns placeholder copy so local development still works, and it logs that it did so.

Only these files are published here. The rest of the application, which I built with a collaborator, isn't included.
