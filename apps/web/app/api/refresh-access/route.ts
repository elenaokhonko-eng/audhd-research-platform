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
    const ticket = await getPlatformApi().refreshAccess(session);
    return json(200, { check: ticket.check });
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
      if (error.code === "terms_required") return json(409, { error: "terms_required" });
      if (error.code === "rate_limited") return json(429, { error: "rate_limited", retry_after: error.retryAfter ?? null });
    }
    return json(503, { error: "unavailable" });
  }
}
