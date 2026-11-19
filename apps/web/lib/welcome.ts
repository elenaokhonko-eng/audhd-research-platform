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
      .filter((r) => r.label === "launch_grant" && r.status === "active" && r.valid_until)
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
