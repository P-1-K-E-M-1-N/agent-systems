/**
 * POST /api/ai/refine — replaces the `refineCopy` mock in services.ts.
 * Body: { action, text, hashtags } → { primary?, hashtags? }.
 */
import { isUnauthenticated } from "@/lib/server/auth";
import { refine } from "@/lib/server/ai";
import type { RefineAction } from "@/lib/services";

const ACTIONS: RefineAction[] = ["shorten", "punchier", "emoji", "hashtags"];

export async function POST(request: Request) {
  if (await isUnauthenticated()) return Response.json({ error: "Unauthorized" }, { status: 401 });

  let body: { action?: unknown; text?: unknown; hashtags?: unknown };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!ACTIONS.includes(body.action as RefineAction)) {
    return Response.json({ error: "Invalid action" }, { status: 400 });
  }

  const text = typeof body.text === "string" ? body.text : "";
  const hashtags = Array.isArray(body.hashtags)
    ? body.hashtags.filter((h): h is string => typeof h === "string")
    : [];

  try {
    const result = await refine(body.action as RefineAction, text, hashtags);
    return Response.json(result);
  } catch (err) {
    console.error("[ai/refine]", err);
    return Response.json({ error: "Refine failed" }, { status: 502 });
  }
}
