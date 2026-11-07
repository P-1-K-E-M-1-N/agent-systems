/**
 * POST /api/ai/custom-refine — replaces the `customRefine` mock in services.ts.
 * Body: { text, instruction } → { text: string }.
 */
import { isUnauthenticated } from "@/lib/server/auth";
import { customRefine } from "@/lib/server/ai";

export async function POST(request: Request) {
  if (await isUnauthenticated()) return Response.json({ error: "Unauthorized" }, { status: 401 });

  let body: { text?: unknown; instruction?: unknown };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const text = typeof body.text === "string" ? body.text : "";
  const instruction = typeof body.instruction === "string" ? body.instruction : "";

  try {
    const result = await customRefine(text, instruction);
    return Response.json({ text: result });
  } catch (err) {
    console.error("[ai/custom-refine]", err);
    return Response.json({ error: "Custom refine failed" }, { status: 502 });
  }
}
