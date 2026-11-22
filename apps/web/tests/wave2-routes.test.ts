// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const fake = new FakePlatformApi();
vi.mock("@/lib/platform-api/client", async (original) => ({
  ...(await original<typeof import("@/lib/platform-api/client")>()),
  getPlatformApi: () => fake,
}));
import { POST as deleteAccount } from "@/app/api/account/delete/route";
import { GET as promotions } from "@/app/api/promotions/route";
import { POST as download } from "@/app/api/library/[sku]/download/route";
import { POST as refreshAccess } from "@/app/api/refresh-access/route";
import { GET as tier } from "@/app/api/tier/route";

const ORIGIN = "https://dev.example.org";
const req = (path: string, headers: Record<string, string>) =>
  new Request(`${ORIGIN}${path}`, { method: "POST", headers });

beforeEach(async () => {
  process.env.SITE_ORIGIN = ORIGIN;
  process.env.SITE_ENV = "dev";
  await fake.resolveSession("fake-token:bo", null);
  await fake.acceptTerms("fake-session:bo", "terms-v1", "privacy-v1");
});

describe("POST /api/account/delete", () => {
  it("deletes, clears the session cookie and ends the session", async () => {
    const res = await deleteAccount(req("/api/account/delete", { origin: ORIGIN, cookie: "session=fake-session:bo" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
    expect(res.headers.get("set-cookie")).toMatch(/^session=;.*Max-Age=0/);
    await expect(fake.me("fake-session:bo")).rejects.toThrow();
  });
  it("refuses another origin", async () =>
    expect((await deleteAccount(req("/api/account/delete", { origin: "https://evil.example", cookie: "session=fake-session:bo" }))).status).toBe(403));
  it("refuses a visitor without a session", async () =>
    expect((await deleteAccount(req("/api/account/delete", { origin: ORIGIN }))).status).toBe(401));
});

describe("POST /api/refresh-access", () => {
  const post = (headers: Record<string, string>) => refreshAccess(req("/api/refresh-access", headers));
  it("starts a check", async () => {
    const res = await post({ origin: ORIGIN, cookie: "session=fake-session:bo" });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ check: "started" });
    expect(res.headers.get("cache-control")).toBe("no-store");
  });
  it("answers 429 with a null retry_after when the service gives none", async () => {
    const { ApiError } = await import("@/lib/platform-api/errors");
    const spy = vi.spyOn(fake, "refreshAccess").mockRejectedValueOnce(new ApiError(429, "rate_limited", "x"));
    const res = await post({ origin: ORIGIN, cookie: "session=fake-session:bo" });
    expect(await res.json()).toEqual({ error: "rate_limited", retry_after: null });
    spy.mockRestore();
  });
  it("refuses another origin", async () =>
    expect((await post({ origin: "https://evil.example", cookie: "session=fake-session:bo" })).status).toBe(403));
  it("refuses a visitor without a session", async () => expect((await post({ origin: ORIGIN })).status).toBe(401));
  it("answers 429 with retry_after when the limit is reached", async () => {
    fake.failNext("rate_limited");
    const res = await post({ origin: ORIGIN, cookie: "session=fake-session:bo" });
    expect(res.status).toBe(429);
    expect(await res.json()).toEqual({ error: "rate_limited", retry_after: 30 });
  });
});

describe("GET /api/tier", () => {
  const get = (headers: Record<string, string>) => tier(new Request(`${ORIGIN}/api/tier`, { headers }));
  it("answers the tier", async () => {
    const res = await get({ cookie: "session=fake-session:bo" });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ tier: "free" });
  });
  it("refuses a visitor without a session", async () => expect((await get({})).status).toBe(401));
  it("answers 409 when the terms are required", async () => {
    fake.failNext("terms_required");
    const res = await get({ cookie: "session=fake-session:bo" });
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({ error: "terms_required" });
  });
});

describe("GET /api/promotions", () => {
  const offer = { id: "p", channel: "substack_offer", plan_interval: "year" as const, starts_at: "2026-11-26T00:00:00Z",
    ends_at: "2026-11-30T23:00:00Z", url: "https://example.org/offer", display: { badge: "Offer", headline: "A headline", body: "A body" } };
  it("answers badge and headline only, cacheable for a minute", async () => {
    fake.setPromotion(offer);
    const res = await promotions();
    expect(await res.json()).toEqual([{ badge: "Offer", headline: "A headline" }]);
    expect(res.headers.get("cache-control")).toBe("public, max-age=60");
    fake.setPromotion(null);
  });
  it("answers an empty list when the service fails", async () => {
    fake.setPromotion(offer);
    fake.failNext("unavailable");
    const res = await promotions();
    expect(await res.json()).toEqual([]);
    expect(res.headers.get("cache-control")).toBe("public, max-age=60");
    fake.setPromotion(null);
  });
});

describe("POST /api/library/[sku]/download", () => {
  const post = (sku: string, headers: Record<string, string>) =>
    download(req(`/api/library/${sku}/download`, headers), { params: Promise.resolve({ sku }) });
  const asBo = { origin: ORIGIN, cookie: "session=fake-session:bo" };
  it("answers 200 with the link for a paid member", async () => {
    await fake.resolveSession("fake-token:ana", null);
    await fake.acceptTerms("fake-session:ana", "terms-v1", "privacy-v1");
    const res = await post("sample-map", { origin: ORIGIN, cookie: "session=fake-session:ana" });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ url: "https://files.invalid/sample-map" });
    expect(res.headers.get("cache-control")).toBe("no-store");
  });
  it("answers 403 with the reason for a free member", async () => {
    const res = await post("sample-map", asBo);
    expect(res.status).toBe(403);
    expect(await res.json()).toEqual({ error: "forbidden", reason: "paid_required" });
  });
  it("answers 404 for a malformed sku without asking the service", async () => {
    const spy = vi.spyOn(fake, "download");
    expect((await post("Sample..Map", asBo)).status).toBe(404);
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
  it("refuses another origin", async () =>
    expect((await post("sample-map", { origin: "https://evil.example", cookie: "session=fake-session:bo" })).status).toBe(403));
  it("refuses a visitor without a session", async () => expect((await post("sample-map", { origin: ORIGIN })).status).toBe(401));
  it("answers 503 when the link is not https", async () => {
    await fake.resolveSession("fake-token:ana", null);
    await fake.acceptTerms("fake-session:ana", "terms-v1", "privacy-v1");
    fake.nextDownloadUrl("http://files.invalid/x");
    const res = await post("sample-map", { origin: ORIGIN, cookie: "session=fake-session:ana" });
    expect(res.status).toBe(503);
    expect(JSON.stringify(await res.json())).not.toContain("files.invalid");
  });
});
