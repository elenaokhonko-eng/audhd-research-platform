import { getPlatformApi } from "@/lib/platform-api/client";

export const dynamic = "force-dynamic";

type Banner = { badge: string; headline: string }[];

const MEMO_MS = 60_000;
let memo: { value: Banner; at: number } | null = null;

// For tests: forget the remembered answer.
export function resetPromotionsMemo(): void {
  memo = null;
}

function list(body: Banner): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json", "cache-control": "public, max-age=60" },
  });
}

// Public: only the words of the banner leave here, never a link, a date or an id.
// The last good answer is kept for a minute so page views do not each call the service; a failure is not kept.
export async function GET(): Promise<Response> {
  const now = Date.now();
  if (memo && now - memo.at < MEMO_MS) return list(memo.value);
  try {
    const promotions = await getPlatformApi().activePromotions();
    const value = promotions.map((p) => ({ badge: p.display.badge, headline: p.display.headline }));
    memo = { value, at: now };
    return list(value);
  } catch {
    return list([]);
  }
}
