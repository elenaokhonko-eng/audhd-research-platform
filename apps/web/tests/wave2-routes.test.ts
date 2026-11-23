// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const fake = new FakePlatformApi();
vi.mock("@/lib/platform-api/client", async (original) => ({
  ...(await original<typeof import("@/lib/platform-api/client")>()),
  getPlatformApi: () => fake,
}));
import { POST as deleteAccount } from "@/app/api/account/delete/route";

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
