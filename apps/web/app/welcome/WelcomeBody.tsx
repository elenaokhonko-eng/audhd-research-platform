import Link from "next/link";
import type { WelcomeView } from "@/lib/welcome";
import { NotRecognised } from "./NotRecognised";
import { SignOutButton } from "./SignOutButton";
import { TermsStep } from "./TermsStep";

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export function WelcomeBody({ view }: { view: WelcomeView | { kind: "unavailable" } }) {
  if (view.kind === "unavailable") {
    return (
      <section className="section-shell join">
        <h1>We could not reach the service. Try again.</h1>
        <p>
          <Link href="/welcome">Try again</Link>
        </p>
      </section>
    );
  }
  if (view.kind === "terms") {
    return (
      <>
        <TermsStep />
        <section className="section-shell join">
          <SignOutButton />
        </section>
      </>
    );
  }
  if (view.kind === "paid") {
    return (
      <section className="section-shell join">
        <h1>You are recognised as a paid subscriber.</h1>
        {view.includedWhilePaying ? <p>Your membership is included for as long as your subscription is active.</p> : null}
        {view.grantUntil ? <p>Your access is guaranteed until {dateFormat.format(new Date(view.grantUntil))}.</p> : null}
        <p>
          <Link className="button button-primary" href="/member">
            Open your workspace
          </Link>
        </p>
        <SignOutButton />
      </section>
    );
  }
  return (
    <section className="section-shell join">
      <h1>You are in as a free member.</h1>
      {view.checking ? (
        <p>
          We are checking your subscription. This can take a minute. <Link href="/welcome">Check again</Link>
        </p>
      ) : null}
      <p>
        <Link href="/upgrade">See how to upgrade</Link>
      </p>
      <NotRecognised />
      <SignOutButton />
    </section>
  );
}
