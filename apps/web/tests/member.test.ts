// @vitest-environment node
import { describe, expect, it } from "vitest";
import { guardMember, navFor } from "@/lib/member";
import { ApiError } from "@/lib/platform-api/errors";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const world = async (name: string, accept = true) => {
  const api = new FakePlatformApi();
  const { session } = await api.resolveSession(`fake-token:${name}`, null);
  if (accept) await api.acceptTerms(session.cookie, "terms-v1", "privacy-v1");
  return { load: (s: string) => api.me(s), s: session.cookie };
};

describe("navFor", () => {
  it("lists a free member's sections in a fixed order", () =>
    expect(navFor(["account", "library", "overview"]).map((n) => n.href)).toEqual(["/member", "/member/library", "/member/account"]));
  it("adds research and guides for a paid member and ignores names it does not know", () =>
    expect(navFor(["overview", "library", "account", "research", "guides", "ask"]).map((n) => n.label)).toEqual(["Overview", "Library", "Research", "Guides", "Account"]));
});

describe("guardMember", () => {
  it("lets a member with accepted terms in", async () => {
    const { load, s } = await world("ana");
    expect((await guardMember(s, load, "research")).kind).toBe("ok");
  });
  it("sends a visitor without a session, or with a dead one, to sign in", async () => {
    const { load } = await world("ana");
    expect(await guardMember(null, load)).toEqual({ kind: "redirect", to: "/join" });
    expect(await guardMember("fake-session:nobody", load)).toEqual({ kind: "redirect", to: "/join" });
  });
  it("sends a member who has not accepted the current terms to the welcome page", async () => {
    const { load, s } = await world("ana", false);
    expect(await guardMember(s, load, "research")).toEqual({ kind: "redirect", to: "/welcome" });
  });
  it("sends a member who accepted an older terms version to the welcome page", async () => {
    const { load, s } = await world("ana");
    const stale = async (x: string) => {
      const me = await load(x);
      return { ...me, member: { ...me.member, terms: { ...me.member.terms, terms_version: "terms-v0" } } };
    };
    expect(await guardMember(s, stale, "research")).toEqual({ kind: "redirect", to: "/welcome" });
  });
  it("sends a free member who types a paid address to the upgrade page", async () => {
    const { load, s } = await world("bo");
    expect(await guardMember(s, load, "research")).toEqual({ kind: "redirect", to: "/upgrade" });
    expect((await guardMember(s, load, "library")).kind).toBe("ok");
  });
  it("reports a service failure without redirecting", async () => {
    const failing = async () => { throw new ApiError(503, "unavailable", "", null); };
    expect(await guardMember("s", failing)).toEqual({ kind: "unavailable" });
  });
});
