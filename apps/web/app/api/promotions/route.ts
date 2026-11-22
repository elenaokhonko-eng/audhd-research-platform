import { getPlatformApi } from "@/lib/platform-api/client";

export const dynamic = "force-dynamic";

function list(body: { badge: string; headline: string }[]): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json", "cache-control": "public, max-age=60" },
  });
}

// Public: only the words of the banner leave here, never a link, a date or an id.
export async function GET(): Promise<Response> {
  try {
    const promotions = await getPlatformApi().activePromotions();
    return list(promotions.map((p) => ({ badge: p.display.badge, headline: p.display.headline })));
  } catch {
    return list([]);
  }
}
