// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const fake = new FakePlatformApi();
vi.mock("@/lib/platform-api/client", async (original) => ({
  ...(await original<typeof import("@/lib/platform-api/client")>()),
  getPlatformApi: () => fake,
}));
import { POST as acceptTerms } from "@/app/api/terms/route";
import { POST as support } from "@/app/api/support/route";

const ORIGIN = "https://dev.example.org";
const req = (path: string, headers: Record<string, string>, body?: unknown) =>
  new Request(`${ORIGIN}${path}`, { method: "POST", headers, body: body ? JSON.stringify(body) : undefined });
const rawReq = (path: string, headers: Record<string, string>, body: string) =>
  new Request(`${ORIGIN}${path}`, { method: "POST", headers, body });

beforeEach(async () => {
  process.env.SITE_ORIGIN = ORIGIN;
  process.env.SITE_ENV = "dev";
  await fake.resolveSession("fake-token:bo", null);
});

describe("POST /api/terms", () => {
  const ok = { origin: ORIGIN, cookie: "session=fake-session:bo", "content-type": "application/json" };
  const current = { terms_version: "terms-v1", privacy_version: "privacy-v1" };
  it("accepts the versions it is sent when they are current", async () => {
    const res = await acceptTerms(req("/api/terms", ok, current));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
    expect((await fake.me("fake-session:bo")).member.terms.accepted).toBe(true);
  });
  it("answers 409 terms_required for stale versions and accepts nothing", async () => {
    await fake.resolveSession("fake-token:ed", null);
    const spy = vi.spyOn(fake, "acceptTerms");
    const res = await acceptTerms(req("/api/terms", { ...ok, cookie: "session=fake-session:ed" }, { terms_version: "terms-v0", privacy_version: "privacy-v1" }));
    expect([res.status, await res.json()]).toEqual([409, { error: "terms_required" }]);
    expect(spy).toHaveBeenCalledWith("fake-session:ed", "terms-v0", "privacy-v1");
    expect((await fake.me("fake-session:ed")).member.terms.accepted).toBe(false);
    spy.mockRestore();
  });
  it("answers 400 validation_failed unless both versions are non-empty strings, and does not call the service", async () => {
    const spy = vi.spyOn(fake, "acceptTerms");
    for (const body of [undefined, {}, { terms_version: "terms-v1" }, { terms_version: "", privacy_version: "privacy-v1" }, { terms_version: 1, privacy_version: "p" }]) {
      const res = await acceptTerms(req("/api/terms", ok, body));
      expect([res.status, await res.json()]).toEqual([400, { error: "validation_failed" }]);
    }
    expect((await acceptTerms(rawReq("/api/terms", ok, "not json"))).status).toBe(400);
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
  it("refuses another origin", async () =>
    expect((await acceptTerms(req("/api/terms", { ...ok, origin: "https://evil.example" }, current))).status).toBe(403));
  it("refuses a visitor without a session", async () =>
    expect((await acceptTerms(req("/api/terms", { origin: ORIGIN }, current))).status).toBe(401));
  it("answers 401 when the service says unauthenticated", async () =>
    expect((await acceptTerms(req("/api/terms", { ...ok, cookie: "session=fake-session:nobody" }, current))).status).toBe(401));
  it("answers 503 on another failure", async () => {
    fake.failNext("unavailable");
    expect((await acceptTerms(req("/api/terms", ok, current))).status).toBe(503);
  });
});

describe("POST /api/support", () => {
  const signInAndAccept = async (name: string) => {
    await fake.resolveSession(`fake-token:${name}`, null);
    await fake.acceptTerms(`fake-session:${name}`, "terms-v1", "privacy-v1");
  };
  it("cuts the note to 500 characters and files it as paid_not_recognised", async () => {
    await signInAndAccept("bo");
    const spy = vi.spyOn(fake, "supportRequest");
    const res = await support(req("/api/support", { origin: ORIGIN, cookie: "session=fake-session:bo" }, { note: "x".repeat(600) }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true });
    expect(spy).toHaveBeenCalledWith("fake-session:bo", "paid_not_recognised", "x".repeat(500));
  });
  it("answers 409 terms_required for a person who has not accepted", async () => {
    await fake.resolveSession("fake-token:ed", null);
    const res = await support(req("/api/support", { origin: ORIGIN, cookie: "session=fake-session:ed" }, { note: "n" }));
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({ error: "terms_required" });
  });
  it("refuses another origin", async () =>
    expect((await support(req("/api/support", { origin: "https://evil.example", cookie: "session=fake-session:bo" }, { note: "n" }))).status).toBe(403));
  it("refuses a visitor without a session", async () =>
    expect((await support(req("/api/support", { origin: ORIGIN }, { note: "n" }))).status).toBe(401));
  it("answers 400 when the body is not JSON or note is not a string", async () => {
    const headers = { origin: ORIGIN, cookie: "session=fake-session:bo" };
    expect((await support(rawReq("/api/support", headers, "not json"))).status).toBe(400);
    expect((await support(req("/api/support", headers, { note: 5 }))).status).toBe(400);
  });
});
