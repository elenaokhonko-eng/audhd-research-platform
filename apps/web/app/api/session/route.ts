import { ApiError, getPlatformApi } from "@/lib/platform-api/client";
import { isSameOrigin } from "@/lib/same-origin";
import { clearSessionCookieHeader, readSessionCookie, sessionCookieHeader } from "@/lib/session";
import { cleanSlug } from "@/lib/slug";

function json(status: number, body: unknown, cookie?: string): Response {
  const headers = new Headers({ "content-type": "application/json", "cache-control": "no-store" });
  if (cookie) headers.set("set-cookie", cookie);
  return new Response(JSON.stringify(body), { status, headers });
}

export async function POST(request: Request): Promise<Response> {
  if (!isSameOrigin(request, process.env.SITE_ORIGIN ?? "")) return json(403, { error: "forbidden" });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json(400, { error: "validation_failed" });
  }
  const fields = (typeof body === "object" && body !== null ? body : {}) as Record<string, unknown>;
  const idToken = fields.id_token;
  if (typeof idToken !== "string" || idToken === "") return json(400, { error: "validation_failed" });

  try {
    const result = await getPlatformApi().resolveSession(idToken, cleanSlug(fields.campaign));
    const cookie = sessionCookieHeader(result.session.cookie, result.session.expires_at, process.env.SITE_ENV ?? "");
    const next = result.join.check === "started" ? "/welcome?check=started" : "/welcome";
    return json(200, { next }, cookie);
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
    if (error instanceof ApiError && error.code === "validation_failed") return json(400, { error: "validation_failed" });
    return json(503, { error: "unavailable" });
  }
}

export async function DELETE(request: Request): Promise<Response> {
  if (!isSameOrigin(request, process.env.SITE_ORIGIN ?? "")) return json(403, { error: "forbidden" });

  const session = readSessionCookie(request.headers.get("cookie"));
  if (session) {
    try {
      await getPlatformApi().revokeSession(session);
    } catch {
      // The cookie is cleared either way; a failed revoke leaves the session to expire on its own.
    }
  }
  const headers = new Headers({
    "set-cookie": clearSessionCookieHeader(process.env.SITE_ENV ?? ""),
    "cache-control": "no-store",
  });
  return new Response(null, { status: 204, headers });
}
