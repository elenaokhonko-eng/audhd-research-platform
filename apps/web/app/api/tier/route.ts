import { ApiError, getPlatformApi } from "@/lib/platform-api/client";
import { readSessionCookie } from "@/lib/session";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

// A read: it changes nothing, so it needs the session but no same-origin check.
export async function GET(request: Request): Promise<Response> {
  const session = readSessionCookie(request.headers.get("cookie"));
  if (!session) return json(401, { error: "unauthenticated" });
  try {
    const { access } = await getPlatformApi().me(session);
    return json(200, { tier: access.tier });
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
    if (error instanceof ApiError && error.code === "terms_required") return json(409, { error: "terms_required" });
    return json(503, { error: "unavailable" });
  }
}
