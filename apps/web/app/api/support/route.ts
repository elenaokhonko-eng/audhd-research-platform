import { ApiError, getPlatformApi } from "@/lib/platform-api/client";
import { isSameOrigin } from "@/lib/same-origin";
import { readSessionCookie } from "@/lib/session";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

export async function POST(request: Request): Promise<Response> {
  if (!isSameOrigin(request, process.env.SITE_ORIGIN ?? "")) return json(403, { error: "forbidden" });
  const session = readSessionCookie(request.headers.get("cookie"));
  if (!session) return json(401, { error: "unauthenticated" });

  let note: unknown;
  try {
    const body: unknown = await request.json();
    note = typeof body === "object" && body !== null ? (body as Record<string, unknown>).note : undefined;
  } catch {
    return json(400, { error: "validation_failed" });
  }
  if (typeof note !== "string") return json(400, { error: "validation_failed" });

  try {
    await getPlatformApi().supportRequest(session, "paid_not_recognised", note.trim().slice(0, 500));
    return json(200, { ok: true });
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
    if (error instanceof ApiError && error.code === "terms_required") return json(409, { error: "terms_required" });
    return json(503, { error: "unavailable" });
  }
}
