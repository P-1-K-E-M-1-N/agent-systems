/**
 * POST /api/ai/generate — replaces the `generateCopy` mock in services.ts.
 * Body: { idea, platforms, tone?, transcript? } → Partial<ComposerDraft>.
 */
import { isUnauthenticated } from "@/lib/server/auth";
import { generate, type GenerateInput } from "@/lib/server/ai";
import { PLATFORM_ORDER, type PlatformId } from "@/lib/platforms";

export async function POST(request: Request) {
  if (await isUnauthenticated()) return Response.json({ error: "Unauthorized" }, { status: 401 });

  let body: Partial<GenerateInput>;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const platforms = Array.isArray(body.platforms)
    ? body.platforms.filter((p): p is PlatformId => PLATFORM_ORDER.includes(p as PlatformId))
    : [];

  if (platforms.length === 0) {
    return Response.json({ error: "At least one valid platform is required" }, { status: 400 });
  }

  try {
    const draft = await generate({
      idea: typeof body.idea === "string" ? body.idea : "",
      platforms,
      tone: body.tone,
      transcript: typeof body.transcript === "string" ? body.transcript : undefined,
    });
    return Response.json(draft);
  } catch (err) {
    console.error("[ai/generate]", err);
    return Response.json({ error: "Generation failed" }, { status: 502 });
  }
}
