import { ApiError, getPlatformApi } from "@/lib/platform-api/client";
import { SKU_PATTERN } from "@/lib/library";
import { isSameOrigin } from "@/lib/same-origin";
import { readSessionCookie } from "@/lib/session";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

function isHttps(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

export async function POST(request: Request, { params }: { params: Promise<{ sku: string }> }): Promise<Response> {
  if (!isSameOrigin(request, process.env.SITE_ORIGIN ?? "")) return json(403, { error: "forbidden" });
  const session = readSessionCookie(request.headers.get("cookie"));
  if (!session) return json(401, { error: "unauthenticated" });
  const { sku } = await params;
  if (!SKU_PATTERN.test(sku)) return json(404, { error: "not_found" });

  try {
    const link = await getPlatformApi().download(session, sku);
    if (!isHttps(link.url)) return json(503, { error: "unavailable" });
    return json(200, { url: link.url });
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.code === "unauthenticated") return json(401, { error: "unauthenticated" });
      if (error.code === "terms_required") return json(409, { error: "terms_required" });
      if (error.status === 403) return json(403, { error: "forbidden", reason: error.reason });
      if (error.status === 404) return json(404, { error: "not_found" });
      if (error.status === 429) return json(429, { error: "rate_limited" });
    }
    return json(503, { error: "unavailable" });
  }
}
