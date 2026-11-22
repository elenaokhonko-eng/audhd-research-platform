import Link from "next/link";
import { navFor, requireMember } from "@/lib/member";

export const dynamic = "force-dynamic";

export default async function MemberOverview() {
  const { access } = await requireMember();
  const links = navFor(access.sections).filter((n) => n.href !== "/member");
  return (
    <main>
      <h1>Your workspace</h1>
      <p>{access.tier === "paid" ? "You have full access." : "You have the free workspace."}</p>
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
