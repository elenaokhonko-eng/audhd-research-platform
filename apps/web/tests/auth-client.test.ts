import { describe, expect, it } from "vitest";
import { createFakeAuthClient, looksLikeSignInLink, toAuthError } from "@/lib/identity/auth-client";
import { identityConfig } from "@/lib/identity/config";

describe("toAuthError", () => {
  it.each([
    ["auth/invalid-email", "invalid_email"],
    ["auth/expired-action-code", "link_expired"],
    ["auth/invalid-action-code", "link_used"],
    ["auth/popup-closed-by-user", "popup_closed"],
    ["auth/cancelled-popup-request", "popup_closed"],
    ["auth/network-request-failed", "network"],
    ["auth/something-new", "unknown"],
  ])("maps %s to %s", (sdkCode, code) => {
    expect(toAuthError({ code: sdkCode }).code).toBe(code);
  });
  it("maps anything that is not an SDK error to unknown", () => {
    expect(toAuthError(new Error("boom")).code).toBe("unknown");
  });
});

describe("fake auth client", () => {
  const client = createFakeAuthClient();
  it("recognises a link by its code", () => {
    expect(client.isEmailLink("https://dev.example.org/auth/finish?oobCode=ok")).toBe(true);
    expect(client.isEmailLink("https://dev.example.org/auth/finish")).toBe(false);
  });
  it("turns an email into a fake token", async () => {
    await expect(client.completeEmailLink("ana@example.org", "https://x/auth/finish?oobCode=ok")).resolves.toBe("fake-token:ana");
  });
  it("fails an expired and a used link the way the real one does", async () => {
    await expect(client.completeEmailLink("ana@example.org", "https://x/?oobCode=expired")).rejects.toMatchObject({ code: "link_expired" });
    await expect(client.completeEmailLink("ana@example.org", "https://x/?oobCode=used")).rejects.toMatchObject({ code: "link_used" });
  });
  it("sends a link without doing anything and signs in with Google as bo", async () => {
    await expect(client.sendEmailLink("ana@example.org", "https://x/auth/finish")).resolves.toBeUndefined();
    await expect(client.signInWithGoogle()).resolves.toBe("fake-token:bo");
  });
});

describe("identityConfig", () => {
  it("is fake only outside prod", () => {
    expect(identityConfig({ PLATFORM_API_FAKE: "1", SITE_ENV: "local" })).toEqual({ kind: "fake", googleEnabled: true });
    expect(identityConfig({ PLATFORM_API_FAKE: "1", SITE_ENV: "prod" })).toEqual({ kind: "missing" });
  });
  it("needs both values", () => {
    expect(identityConfig({ IDENTITY_API_KEY: "k", IDENTITY_AUTH_DOMAIN: "d.example" })).toEqual({ kind: "firebase", apiKey: "k", authDomain: "d.example", googleEnabled: false });
    expect(identityConfig({ IDENTITY_API_KEY: "k" })).toEqual({ kind: "missing" });
  });
});

describe("real client link check (no SDK needed)", () => {
  it("accepts only a sign-in link with a code", () => {
    expect(looksLikeSignInLink("https://dev.example.org/auth/finish?mode=signIn&oobCode=abc")).toBe(true);
    expect(looksLikeSignInLink("https://dev.example.org/auth/finish?oobCode=abc")).toBe(false);
    expect(looksLikeSignInLink("https://dev.example.org/auth/finish?mode=signIn&oobCode=")).toBe(false);
    expect(looksLikeSignInLink("not a url")).toBe(false);
  });
});
