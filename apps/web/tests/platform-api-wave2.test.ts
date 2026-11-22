// tests/platform-api-wave2.test.ts
// @vitest-environment node
import { describe, expect, it } from "vitest";
import { HttpPlatformApi } from "@/lib/platform-api/client";
import { ApiError } from "@/lib/platform-api/errors";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const signedIn = async (name: string, accept = true) => {
  const api = new FakePlatformApi();
  const { session } = await api.resolveSession(`fake-token:${name}`, null);
  if (accept) await api.acceptTerms(session.cookie, "terms-v1", "privacy-v1");
  return { api, s: session.cookie };
};
const code = async (p: Promise<unknown>) => p.then(() => "ok", (e) => (e instanceof ApiError ? `${e.code}:${e.reason}` : "other"));

describe("FakePlatformApi, second wave", () => {
  it("shows a free member every card and what is locked", async () => {
    const { api, s } = await signedIn("bo");
    expect((await api.libraryItems(s)).map((i) => [i.sku, i.can_open])).toEqual([["sample-book", false], ["sample-guide", true], ["sample-map", false]]);
  });
  it("lets a paid member download and tells a free member why not", async () => {
    const ana = await signedIn("ana");
    expect((await ana.api.download(ana.s, "sample-map")).url).toBe("https://files.invalid/sample-map");
    const bo = await signedIn("bo");
    expect(await code(bo.api.download(bo.s, "sample-map"))).toBe("forbidden:paid_required");
    expect(await code(bo.api.download(bo.s, "sample-book"))).toBe("forbidden:purchase_required");
    expect(await code(bo.api.download(bo.s, "nope"))).toBe("not_found:null");
  });
  it("offers each kind of member the right upgrade route", async () => {
    const bo = await signedIn("bo");
    expect((await bo.api.upgradeOptions(bo.s)).routes.map((r) => [r.kind, r.available])).toEqual([["substack", true], ["platform_only", false]]);
    const hal = await signedIn("hal");
    expect(await hal.api.upgradeOptions(hal.s)).toEqual({ routes: [{ kind: "substack_change_plan", available: true, url: "https://example.org/subscribe" }], promotion: null });
    const ana = await signedIn("ana");
    expect(await ana.api.upgradeOptions(ana.s)).toEqual({ routes: [], promotion: null });
  });
  it("puts an active promotion on the free member's route only", async () => {
    const { api, s } = await signedIn("bo");
    api.setPromotion({ id: "p", channel: "substack_offer", plan_interval: "year", starts_at: "2026-01-01T00:00:00Z", ends_at: "2026-01-02T00:00:00Z",
      url: "https://example.org/offer", display: { badge: "b", headline: "h", body: "x" } });
    const options = await api.upgradeOptions(s);
    expect([options.routes[0].url, options.promotion?.id]).toEqual(["https://example.org/offer", "p"]);
    expect(await api.activePromotions()).toHaveLength(1);
  });
  it("turns a member paid after a refresh when the test says so", async () => {
    const { api, s } = await signedIn("bo");
    api.upgradeAfterRefresh("bo");
    expect((await api.refreshAccess(s)).check).toBe("started");
    expect((await api.me(s)).access.tier).toBe("paid");
    expect((await api.refreshAccess(s)).check).toBe("already_running");
  });
  it("asks for the terms on gated routes and ends the session on deletion", async () => {
    const { api, s } = await signedIn("bo", false);
    expect(await code(api.libraryItems(s))).toBe("terms_required:null");
    await api.requestDeletion(s);
    expect(await code(api.me(s))).toBe("unauthenticated:null");
  });
});

describe("HttpPlatformApi, second wave", () => {
  const respond = (status: number, body: unknown) => async () => new Response(JSON.stringify(body), { status });
  const api = (f: typeof fetch) => new HttpPlatformApi("https://api.example.org", async () => "tok", f);
  it("accepts 202 from refresh-access and reads the ticket", async () => {
    const ticket = { check: "started", last_completed_at: null, next_allowed_at: "2026-11-20T00:01:00Z" };
    expect(await api(respond(202, ticket) as typeof fetch).refreshAccess("s")).toEqual(ticket);
  });
  it("carries the reason of a refused download", async () => {
    const body = { error: { code: "forbidden", message: "Not included.", retry_after: null, reason: "paid_required" } };
    expect(await code(api(respond(403, body) as typeof fetch).download("s", "sample-map"))).toBe("forbidden:paid_required");
  });
  it("encodes the sku and sends the session header", async () => {
    let seen: Request | undefined;
    const f = (async (url: string, init: RequestInit) => { seen = new Request(url, init); return new Response(JSON.stringify({ item: {}, description: "", citation: null })); }) as unknown as typeof fetch;
    await api(f).libraryItem("s-1", "a/b");
    expect([seen?.url, seen?.headers.get("x-member-session")]).toEqual(["https://api.example.org/v1/library/items/a%2Fb", "s-1"]);
  });
});
