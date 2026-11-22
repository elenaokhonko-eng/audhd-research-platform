import { formatDate } from "@/lib/reasons";
import type { Access, UpgradeOptions } from "@/lib/platform-api/types";

export type UpgradeView =
  | { kind: "paid" }
  | { kind: "change_plan"; url: string | null; planInterval: "month" | "year" | null }
  | { kind: "subscribe"; url: string | null; offer: { badge: string; headline: string; body: string; ends: string | null } | null };

export function upgradeView(access: Access, options: UpgradeOptions): UpgradeView {
  if (access.tier === "paid") return { kind: "paid" };
  const route = (kind: string) => options.routes.find((r) => r.kind === kind);
  const urlOf = (kind: string) => {
    const r = route(kind);
    return r && r.available ? r.url : null;
  };
  if (route("substack_change_plan")) {
    const live = access.reasons.find(
      (r) => r.label === "substack_status" && (r.status === "active" || r.status === "grace"),
    );
    return { kind: "change_plan", url: urlOf("substack_change_plan"), planInterval: live?.plan_interval ?? null };
  }
  const p = options.promotion;
  return {
    kind: "subscribe",
    url: urlOf("substack"),
    offer: p ? { badge: p.display.badge, headline: p.display.headline, body: p.display.body, ends: formatDate(p.ends_at) } : null,
  };
}

export async function pollUntilPaid(opts: {
  tier: () => Promise<"free" | "paid" | "signed_out">;
  sleep: (ms: number) => Promise<void>;
  everyMs?: number;
  forMs?: number;
}): Promise<"paid" | "timeout" | "signed_out"> {
  const every = opts.everyMs ?? 5000;
  const total = opts.forMs ?? 60000;
  let slept = 0;
  for (;;) {
    try {
      const answer = await opts.tier();
      if (answer === "paid" || answer === "signed_out") return answer;
    } catch {
      // A failed request counts as "not yet".
    }
    if (slept >= total) return "timeout";
    await opts.sleep(every);
    slept += every;
  }
}
