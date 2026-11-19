import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionError, defaultPostSession, isRetryable } from "@/lib/identity/session-client";
import { defaultSignOut, leaveToJoin } from "@/lib/identity/sign-out";

afterEach(() => vi.unstubAllGlobals());
beforeEach(() => localStorage.clear());

describe("defaultPostSession", () => {
  it("returns where to go next on 200", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ next: "/welcome" }), { status: 200 })));
    await expect(defaultPostSession("fake-token:ana", "founding")).resolves.toEqual({ next: "/welcome" });
  });
  it.each([400, 401, 503])("throws an error carrying the status %s", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status })));
    const error = await defaultPostSession("fake-token:ana", null).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SessionError);
    expect((error as SessionError).status).toBe(status);
  });
});

describe("isRetryable", () => {
  it("retries a 503 and a failure without a status", () => {
    expect(isRetryable(new SessionError(503))).toBe(true);
    expect(isRetryable(new TypeError("network"))).toBe(true);
  });
  it.each([400, 401])("does not retry %s", (status) => expect(isRetryable(new SessionError(status))).toBe(false));
});

describe("sign-out", () => {
  it("sends DELETE /api/session to the same origin", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    await defaultSignOut();
    expect(fetch).toHaveBeenCalledWith("/api/session", { method: "DELETE", credentials: "same-origin" });
  });
  it("forgets the stored address and goes to /join even when the sign-out fails", async () => {
    localStorage.setItem("signin.email", "ana@example.org");
    const go = vi.fn();
    await leaveToJoin(vi.fn().mockRejectedValue(new Error("x")), go);
    expect(go).toHaveBeenCalledWith("/join");
    expect(localStorage.getItem("signin.email")).toBeNull();
  });
});
