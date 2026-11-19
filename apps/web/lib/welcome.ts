import { ApiError } from "@/lib/platform-api/errors";
import type { Access, Member } from "@/lib/platform-api/types";

export type WelcomeView =
  | { kind: "terms" }
  | { kind: "paid"; grantUntil: string | null; includedWhilePaying: boolean }
  | { kind: "free"; checking: boolean };

export function welcomeView(me: { member: Member; access: Access }, check: string | null): WelcomeView {
  if (!me.member.terms.accepted) return { kind: "terms" };
  if (me.access.tier === "paid") {
    const reasons = me.access.reasons;
    const dates = reasons
      .filter((r) => r.label === "launch_grant" && r.status === "active" && r.valid_until && !Number.isNaN(Date.parse(r.valid_until)))
      .map((r) => r.valid_until as string)
      .sort((a, b) => Date.parse(a) - Date.parse(b));
    return {
      kind: "paid",
      grantUntil: dates.length ? dates[dates.length - 1] : null,
      includedWhilePaying: reasons.some(
        (r) => r.label === "substack_subscription" && (r.status === "active" || r.status === "grace"),
      ),
    };
  }
  return { kind: "free", checking: check === "started" };
}

export type WelcomeState = WelcomeView | { kind: "signin" } | { kind: "unavailable" };

// What /welcome shows: the member's view, sign-in when the session is not valid, or a soft failure
// when the service could not answer. Never throws, so the page never falls to the generic error page.
export async function welcomeState(
  loadMe: () => Promise<{ member: Member; access: Access }>,
  check: string | null,
): Promise<WelcomeState> {
  let me;
  try {
    me = await loadMe();
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") return { kind: "signin" };
    return { kind: "unavailable" };
  }
  return welcomeView(me, check);
}
