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

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json(400, { error: "validation_failed" });
  }
  const { terms_version: terms, privacy_version: privacy } = (body ?? {}) as Record<string, unknown>;
  if (typeof terms !== "string" || terms === "" || typeof privacy !== "string" || privacy === "")
    return json(400, { error: "validation_failed" });

  try {
    await getPlatformApi().acceptTerms(session, terms, privacy);
    return json(200, { ok: true });
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
    // The versions the person saw are no longer the required ones: ask again with the new ones.
    if (error instanceof ApiError && error.code === "validation_failed") return json(409, { error: "terms_required" });
    return json(503, { error: "unavailable" });
  }
}
