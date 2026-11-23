import Link from "next/link";
import { overviewCounts } from "@/lib/library";
import { navFor, requireMember, sessionForRequest } from "@/lib/member";
import { getPlatformApi } from "@/lib/platform-api/client";
import { LibraryCount } from "./components/LibraryCount";

export const dynamic = "force-dynamic";

export default async function MemberOverview() {
  const { access } = await requireMember();
  const counts = await overviewCounts(sessionForRequest, (session) => getPlatformApi().libraryItems(session));
  const links = navFor(access.sections).filter((n) => n.href !== "/member");
  return (
    <main>
      <h1>Your workspace</h1>
      <p>{access.tier === "paid" ? "You have full access." : "You have the free workspace."}</p>
      <LibraryCount counts={counts} tier={access.tier} />
      <ul>
        {links.map((n) => (
          <li key={n.href}>
            <Link href={n.href}>{n.label}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
