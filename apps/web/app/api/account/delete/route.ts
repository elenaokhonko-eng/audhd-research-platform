import { ApiError, getPlatformApi } from "@/lib/platform-api/client";
import { isSameOrigin } from "@/lib/same-origin";
import { clearSessionCookieHeader, readSessionCookie } from "@/lib/session";

function json(status: number, body: unknown, extra: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store", ...extra },
  });
}

export async function POST(request: Request): Promise<Response> {
  if (!isSameOrigin(request, process.env.SITE_ORIGIN ?? "")) return json(403, { error: "forbidden" });
  const session = readSessionCookie(request.headers.get("cookie"));
  if (!session) return json(401, { error: "unauthenticated" });

  try {
    await getPlatformApi().requestDeletion(session);
    return json(200, { ok: true }, { "set-cookie": clearSessionCookieHeader(process.env.SITE_ENV ?? "") });
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
    if (error instanceof ApiError && error.code === "terms_required") return json(409, { error: "terms_required" });
    return json(503, { error: "unavailable" });
  }
}
