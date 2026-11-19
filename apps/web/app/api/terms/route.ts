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

  try {
    const api = getPlatformApi();
    const { member } = await api.me(session);
    await api.acceptTerms(session, member.terms.required.terms_version, member.terms.required.privacy_version);
    return json(200, { ok: true });
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
    return json(503, { error: "unavailable" });
  }
}
