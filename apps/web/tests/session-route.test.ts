// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakePlatformApi } from "@/lib/platform-api/fake";
import { cleanSlug } from "@/lib/slug";
import { isSameOrigin } from "@/lib/same-origin";
import { readSessionCookie, sessionCookieHeader } from "@/lib/session";

const fake = new FakePlatformApi();
vi.mock("@/lib/platform-api/client", async (original) => ({
  ...(await original<typeof import("@/lib/platform-api/client")>()),
  getPlatformApi: () => fake,
}));
import { DELETE, POST } from "@/app/api/session/route";

const ORIGIN = "https://dev.example.org";
const post = (body: unknown, headers: Record<string, string> = { origin: ORIGIN }) =>
  POST(new Request(`${ORIGIN}/api/session`, { method: "POST", headers, body: JSON.stringify(body) }));

beforeEach(() => {
  process.env.SITE_ORIGIN = ORIGIN;
  process.env.SITE_ENV = "dev";
});

describe("cleanSlug", () => {
  it.each([["founding", "founding"], ["a-1", "a-1"]])("keeps %s", (input, output) => {
    expect(cleanSlug(input)).toBe(output);
  });
  it.each(["../admin", "Founding", "", "a".repeat(41), "<b>", 7, null, undefined])("drops %s", (input) => {
    expect(cleanSlug(input)).toBeNull();
  });
});

describe("isSameOrigin", () => {
  const req = (headers: Record<string, string>) => new Request(`${ORIGIN}/api/x`, { method: "POST", headers });
  it("accepts the site's own origin", () => expect(isSameOrigin(req({ origin: ORIGIN }), ORIGIN)).toBe(true));
  it("refuses another origin", () => expect(isSameOrigin(req({ origin: "https://evil.example" }), ORIGIN)).toBe(false));
  it("accepts same-origin fetch metadata when Origin is absent", () =>
    expect(isSameOrigin(req({ "sec-fetch-site": "same-origin" }), ORIGIN)).toBe(true));
  it("refuses when both are absent", () => expect(isSameOrigin(req({}), ORIGIN)).toBe(false));
});

describe("session cookie", () => {
  it("is http-only, lax, secure outside local, and expires when the session does", () => {
    const header = sessionCookieHeader("abc", "2026-12-01T00:00:00Z", "dev");
    expect(header).toContain("session=abc");
    expect(header).toContain("HttpOnly");
    expect(header).toContain("SameSite=Lax");
    expect(header).toContain("Path=/");
    expect(header).toContain("Secure");
    expect(header).toContain("Expires=Tue, 01 Dec 2026 00:00:00 GMT");
    expect(sessionCookieHeader("abc", "2026-12-01T00:00:00Z", "local")).not.toContain("Secure");
  });
  it("is read back from a cookie header", () => {
    expect(readSessionCookie("a=1; session=abc; b=2")).toBe("abc");
    expect(readSessionCookie(null)).toBeNull();
  });
});

describe("POST /api/session", () => {
  it("sets the cookie and sends a recognised reader to the welcome page", async () => {
    const res = await post({ id_token: "fake-token:ana", campaign: "founding" });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ next: "/welcome" });
    expect(res.headers.get("set-cookie")).toContain("session=fake-session:ana");
  });
  it("drops a slug that is not a slug", async () => {
    const spy = vi.spyOn(fake, "resolveSession");
    await post({ id_token: "fake-token:bo", campaign: "../admin" });
    expect(spy).toHaveBeenLastCalledWith("fake-token:bo", null);
  });
  it("refuses another origin and sets no cookie", async () => {
    const res = await post({ id_token: "fake-token:ana", campaign: null }, { origin: "https://evil.example" });
    expect(res.status).toBe(403);
    expect(res.headers.get("set-cookie")).toBeNull();
  });
  it("answers 400 without a token", async () => {
    expect((await post({ campaign: null })).status).toBe(400);
  });
  it("answers 400 when the body is not JSON", async () => {
    const res = await POST(new Request(`${ORIGIN}/api/session`, { method: "POST", headers: { origin: ORIGIN }, body: "not json" }));
    expect(res.status).toBe(400);
  });
  it("answers 401 for a token the service rejects", async () => {
    const res = await post({ id_token: "nonsense", campaign: null });
    expect(res.status).toBe(401);
    expect(res.headers.get("set-cookie")).toBeNull();
  });
  it("answers 503 and sets no cookie when the service cannot be reached", async () => {
    fake.failNext("unavailable");
    const res = await post({ id_token: "fake-token:ana", campaign: null });
    expect(res.status).toBe(503);
    expect(res.headers.get("set-cookie")).toBeNull();
  });
  it("never puts the token in the answer", async () => {
    const res = await post({ id_token: "nonsense-token-value", campaign: null });
    expect(await res.text()).not.toContain("nonsense-token-value");
  });
});

describe("DELETE /api/session", () => {
  it("clears the cookie even when revoking fails", async () => {
    fake.failNext("unavailable");
    const res = await DELETE(
      new Request(`${ORIGIN}/api/session`, { method: "DELETE", headers: { origin: ORIGIN, cookie: "session=fake-session:bo" } }),
    );
    expect(res.status).toBe(204);
    expect(res.headers.get("set-cookie")).toContain("session=;");
  });
});
