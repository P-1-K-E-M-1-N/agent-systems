/**
 * POST /api/ai/variations — replaces the `generateVariations` mock in services.ts.
 * Body: { idea, tone } → { variations: string[] }.
 */
import { isUnauthenticated } from "@/lib/server/auth";
import { variations } from "@/lib/server/ai";
import type { Tone } from "@/lib/services";

export async function POST(request: Request) {
  if (await isUnauthenticated()) return Response.json({ error: "Unauthorized" }, { status: 401 });

  let body: { idea?: unknown; tone?: unknown };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const idea = typeof body.idea === "string" ? body.idea : "";
  const tone = (typeof body.tone === "string" ? body.tone : "punchy") as Tone;

  try {
    const items = await variations(idea, tone);
    return Response.json({ variations: items });
  } catch (err) {
    console.error("[ai/variations]", err);
    return Response.json({ error: "Variations failed" }, { status: 502 });
  }
}
