import { cache } from "react";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { getPlatformApi } from "@/lib/platform-api/client";
import { ApiError } from "@/lib/platform-api/errors";
import type { Access, Member } from "@/lib/platform-api/types";
import { readSessionCookie } from "@/lib/session";
import { termsCurrent } from "@/lib/welcome";

export type Section = "overview" | "library" | "research" | "guides" | "account";

export const SECTION_ROUTES: Record<Section, { href: string; label: string }> = {
  overview: { href: "/member", label: "Overview" },
  library: { href: "/member/library", label: "Library" },
  research: { href: "/member/research", label: "Research" },
  guides: { href: "/member/guides", label: "Guides" },
  account: { href: "/member/account", label: "Account" },
};

export type Me = { member: Member; access: Access };

export function navFor(sections: string[]): { href: string; label: string }[] {
  const have = new Set(sections);
  return (Object.keys(SECTION_ROUTES) as Section[]).filter((s) => have.has(s)).map((s) => SECTION_ROUTES[s]);
}

export type Guard = { kind: "ok"; me: Me } | { kind: "redirect"; to: string } | { kind: "unavailable" };

export async function guardMember(
  session: string | null,
  loadMe: (s: string) => Promise<Me>,
  section?: Section,
): Promise<Guard> {
  if (!session) return { kind: "redirect", to: "/join" };
  let me: Me;
  try {
    me = await loadMe(session);
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return { kind: "redirect", to: "/join" };
    return { kind: "unavailable" };
  }
  if (!termsCurrent(me.member)) return { kind: "redirect", to: "/welcome" };
  if (section && !me.access.sections.includes(section)) return { kind: "redirect", to: "/upgrade" };
  return { kind: "ok", me };
}

// One load per request: the layout and the page share this result.
const loadForRequest = cache(async (): Promise<{ session: string | null; result: { me: Me } | { failed: unknown } }> => {
  const session = readSessionCookie((await headers()).get("cookie"));
  if (!session) return { session, result: { failed: null } };
  try {
    return { session, result: { me: await getPlatformApi().me(session) } };
  } catch (error) {
    return { session, result: { failed: error } };
  }
});

export async function guardForRequest(section?: Section): Promise<Guard> {
  const { session, result } = await loadForRequest();
  return guardMember(
    session,
    async () => {
      if ("me" in result) return result.me;
      throw result.failed;
    },
    section,
  );
}

export async function requireMember(section?: Section): Promise<Me> {
  const guard = await guardForRequest(section);
  if (guard.kind === "redirect") redirect(guard.to);
  if (guard.kind === "unavailable") throw new Error("unavailable");
  return guard.me;
}

// The session the guard used, for pages that call the service after requireMember.
export async function sessionForRequest(): Promise<string> {
  const { session } = await loadForRequest();
  if (!session) redirect("/join");
  return session;
}
