// tests/upgrade.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CheckAgain } from "@/app/upgrade/CheckAgain";
import type { Access, UpgradeOptions } from "@/lib/platform-api/types";
import { pollUntilPaid, upgradeView } from "@/lib/upgrade";

const promotion = { id: "p", channel: "substack_offer", plan_interval: "year" as const, starts_at: "2026-11-26T00:00:00Z", ends_at: "2026-11-30T23:00:00Z",
  url: "https://example.org/offer", display: { badge: "Offer", headline: "A headline", body: "A body" } };
const free = (over: Partial<UpgradeOptions> = {}): UpgradeOptions => ({
  routes: [{ kind: "substack", available: true, url: "https://example.org/subscribe" }, { kind: "platform_only", available: false, url: null }], promotion: null, ...over });

const access = (tier: "free" | "paid", interval?: "month" | "year" | null): Access => ({ tier, sections: [], items: [], computed_at: "2026-11-20T00:00:00Z",
  reasons: interval === undefined ? [] : [{ grant: "status:substack_paid", source: "substack_stripe", label: "substack_status", access_scope: "substack+platform",
    status: "active", valid_until: null, campaign: null, plan_interval: interval }] });
const changePlan: UpgradeOptions = { routes: [{ kind: "substack_change_plan", available: true, url: "https://example.org/subscribe" }], promotion: null };

describe("upgradeView", () => {
  it("shows a paid member nothing to buy", () => expect(upgradeView(access("paid"), { routes: [], promotion: null })).toEqual({ kind: "paid" }));
  it("shows a monthly payer how to change plan and no offer", () =>
    expect(upgradeView(access("free", "month"), changePlan)).toEqual({ kind: "change_plan", url: "https://example.org/subscribe", planInterval: "month" }));
  it("does not call a complimentary reader a monthly payer", () =>
    expect(upgradeView(access("free", null), changePlan)).toEqual({ kind: "change_plan", url: "https://example.org/subscribe", planInterval: null }));
  it("shows a free member the subscribe route, with the offer and its end when there is one", () => {
    expect(upgradeView(access("free"), free())).toEqual({ kind: "subscribe", url: "https://example.org/subscribe", offer: null });
    const withOffer = upgradeView(access("free"), free({ routes: [{ kind: "substack", available: true, url: promotion.url }], promotion }));
    expect(withOffer).toEqual({ kind: "subscribe", url: "https://example.org/offer", offer: { badge: "Offer", headline: "A headline", body: "A body", ends: "30 November 2026" } });
  });
  it("gives no link when the route is not available", () =>
    expect(upgradeView(access("free"), { routes: [{ kind: "substack", available: false, url: null }], promotion: null })).toEqual({ kind: "subscribe", url: null, offer: null }));
});

describe("pollUntilPaid", () => {
  const clock = () => { const slept: number[] = []; return { slept, sleep: async (ms: number) => { slept.push(ms); } }; };
  it("stops as soon as the member is paid", async () => {
    const { slept, sleep } = clock();
    const answers = ["free", "free", "paid"] as const;
    let i = 0;
    expect(await pollUntilPaid({ tier: async () => answers[i++], sleep })).toBe("paid");
    expect(slept).toEqual([5000, 5000]);
  });
  it("gives up after a minute", async () => {
    const { slept, sleep } = clock();
    expect(await pollUntilPaid({ tier: async () => "free", sleep })).toBe("timeout");
    expect(slept.reduce((a, b) => a + b, 0)).toBe(60000);
  });
  it("treats a failed request as not yet, and stops when signed out", async () => {
    const { sleep } = clock();
    let n = 0;
    expect(await pollUntilPaid({ tier: async () => { if (n++ === 0) throw new Error("network"); return "signed_out"; }, sleep })).toBe("signed_out");
  });
});

describe("CheckAgain", () => {
  afterEach(() => vi.unstubAllGlobals());
  const respond = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });
  it("starts a check, then reports that nothing was found after the time is up", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === "/api/refresh-access" ? respond(200, { check: "started" }) : respond(200, { tier: "free" }))));
    render(<CheckAgain sleep={async () => {}} onPaid={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByText(/We did not find a paid subscription for this address yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeEnabled();
  });
  it("reloads when the member has become paid", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === "/api/refresh-access" ? respond(200, { check: "started" }) : respond(200, { tier: "paid" }))));
    const onPaid = vi.fn();
    render(<CheckAgain sleep={async () => {}} onPaid={onPaid} />);
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    await vi.waitFor(() => expect(onPaid).toHaveBeenCalledOnce());
  });
  it("asks the member to wait when the limit is reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(429, { error: "rate_limited", retry_after: 30 })));
    render(<CheckAgain sleep={async () => {}} onPaid={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Please wait a moment before checking again.");
  });
});
