import Link from "next/link";
import { requireMember } from "@/lib/member";
import { reasonText } from "@/lib/reasons";
import { DeleteAccount } from "../components/DeleteAccount";

export const dynamic = "force-dynamic";
export const metadata = { title: "Account", robots: { index: false } };

export default async function AccountPage() {
  const { member, access } = await requireMember("account");
  return (
    <main>
      <h1>Account</h1>
      <p>Signed in as {member.email_hint}</p>

      <section aria-labelledby="access-heading">
        <h2 id="access-heading">Your access</h2>
        <p>{access.tier === "paid" ? "Full access" : "Free workspace"}</p>
        {access.reasons.length > 0 ? (
          <ul>
            {access.reasons.map((reason, index) => (
              <li key={`${reason.grant}-${index}`}>{reasonText(reason)}</li>
            ))}
          </ul>
        ) : null}
        {access.tier === "free" ? (
          <p>
            <Link href="/upgrade">See how to upgrade</Link>
          </p>
        ) : null}
      </section>

      <section aria-labelledby="terms-heading">
        <h2 id="terms-heading">Terms</h2>
        <p>
          You accepted <Link href="/terms">terms</Link> version {member.terms.terms_version} and the{" "}
          <Link href="/privacy">privacy notice</Link> version {member.terms.privacy_version}.
        </p>
      </section>

      <section aria-labelledby="delete-heading">
        <h2 id="delete-heading">Delete your account</h2>
        <p>This removes your account and your records within 30 days. It does not cancel a Substack subscription.</p>
        <DeleteAccount />
      </section>
    </main>
  );
}
