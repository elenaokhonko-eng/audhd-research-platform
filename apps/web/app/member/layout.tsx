import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { guardForRequest, navFor } from "@/lib/member";
import { SignOutButton } from "../welcome/SignOutButton";
import { WorkspaceNav } from "./components/WorkspaceNav";

export const dynamic = "force-dynamic";
export const metadata = { title: "Member workspace", robots: { index: false } };

export default async function MemberLayout({ children }: { children: ReactNode }) {
  // A layout's own error boundary is not reached by its own throw, so this layout never throws.
  const guard = await guardForRequest();
  if (guard.kind === "redirect") redirect(guard.to);

  if (guard.kind === "unavailable") {
    return (
      <div className="member-shell">
        <div className="member-main">
          <div className="member-content">
            <p role="status">The member area cannot be reached right now. Please try again in a minute.</p>
            <p>
              <Link href="/member">Try again</Link>
            </p>
          </div>
        </div>
      </div>
    );
  }

  const { member, access } = guard.me;
  return (
    <div className="member-shell">
      <aside className="member-sidebar">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">A</span>
          <span>AuDHD Research</span>
        </Link>
        <WorkspaceNav items={navFor(access.sections)} />
        <div className="member-sidebar-bottom">
          <small>{member.email_hint}</small>
          {access.tier === "free" ? <Link href="/upgrade">Upgrade</Link> : null}
          <SignOutButton />
        </div>
      </aside>
      <div className="member-main">
        <div className="member-content">{children}</div>
      </div>
    </div>
  );
}
