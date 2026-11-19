import { describe, expect, it, vi } from "vitest";
import { ApiError, HttpPlatformApi, getPlatformApi } from "@/lib/platform-api/client";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("HttpPlatformApi", () => {
  it("sends the service token and the member session", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json(200, { member: {}, access: {} }));
    const api = new HttpPlatformApi("https://api.internal", async () => "svc-token", fetchImpl);
    await api.me("sess-1");
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("https://api.internal/v1/me");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer svc-token");
    expect(new Headers(init.headers).get("x-member-session")).toBe("sess-1");
  });

  it("posts the token and the campaign to session resolve, without a member session", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json(200, { session: {}, member: {}, access: {}, join: {} }));
    const api = new HttpPlatformApi("https://api.internal", async () => "svc-token", fetchImpl);
    await api.resolveSession("id-token", "founding");
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("https://api.internal/v1/session/resolve");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ id_token: "id-token", campaign: "founding" });
    expect(new Headers(init.headers).has("x-member-session")).toBe(false);
  });

  it("turns the error body into an ApiError", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      json(429, { error: { code: "rate_limited", message: "Too many requests", retry_after: 30 } }),
    );
    const api = new HttpPlatformApi("https://api.internal", async () => "t", fetchImpl);
    await expect(api.me("s")).rejects.toMatchObject({ status: 429, code: "rate_limited", retryAfter: 30 });
  });

  it("reports unavailable when the call fails or times out", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("network down"));
    const api = new HttpPlatformApi("https://api.internal", async () => "t", fetchImpl);
    await expect(api.me("s")).rejects.toMatchObject({ status: 503, code: "unavailable" });
  });

  it("asks the default campaign when there is no slug", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json(200, { slug: null, state: "open", copy: {} }));
    const api = new HttpPlatformApi("https://api.internal", async () => "t", fetchImpl);
    await api.campaign(null);
    expect(fetchImpl.mock.calls[0][0]).toBe("https://api.internal/v1/public/campaigns/default");
  });
});

describe("getPlatformApi", () => {
  it("refuses the fake in prod", () => {
    expect(() => getPlatformApi({ PLATFORM_API_FAKE: "1", SITE_ENV: "prod" })).toThrow(/not allowed in prod/);
  });
  it("gives the fake elsewhere", () => {
    expect(getPlatformApi({ PLATFORM_API_FAKE: "1", SITE_ENV: "dev" })).toBeInstanceOf(FakePlatformApi);
  });
  it("needs a URL for the real client", () => {
    expect(() => getPlatformApi({ SITE_ENV: "dev" })).toThrow(/PLATFORM_API_URL is not set/);
  });
});

describe("FakePlatformApi", () => {
  it("recognises ana as paid with a launch grant", async () => {
    const result = await new FakePlatformApi().resolveSession("fake-token:ana", "founding");
    expect(result.session.cookie).toBe("fake-session:ana");
    expect(result.join).toMatchObject({ campaign: "founding", recognition: "paid" });
    expect(result.join.grant?.created).toBe(true);
    expect(result.access.reasons.map((r) => r.label).sort()).toEqual(["launch_grant", "substack_subscription"]);
  });
  it("gives bo the free workspace", async () => {
    const result = await new FakePlatformApi().resolveSession("fake-token:bo", null);
    expect(result.join.recognition).toBe("free");
    expect(result.access.tier).toBe("free");
  });
  it("rejects an unknown token as unauthenticated", async () => {
    await expect(new FakePlatformApi().resolveSession("nonsense", null)).rejects.toBeInstanceOf(ApiError);
  });
  it("fails the next call on request", async () => {
    const fake = new FakePlatformApi();
    await fake.resolveSession("fake-token:bo", null);
    fake.failNext("unavailable");
    await expect(fake.me("fake-session:bo")).rejects.toMatchObject({ code: "unavailable" });
    await expect(fake.me("fake-session:bo")).resolves.toBeTruthy();
  });
  it("returns the default campaign for an unknown slug and a closed one on request", async () => {
    const fake = new FakePlatformApi();
    expect((await fake.campaign("no-such")).slug).toBeNull();
    expect((await fake.campaign("closed")).state).toBe("closed");
  });
});
