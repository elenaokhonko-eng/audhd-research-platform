import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { getPlatformApi } from "@/lib/platform-api/client";
import type { UpgradeOptions } from "@/lib/platform-api/types";
import { guardMember } from "@/lib/member";
import { readSessionCookie } from "@/lib/session";
import { upgradeView } from "@/lib/upgrade";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { CheckAgain } from "./CheckAgain";

export const dynamic = "force-dynamic";
export const metadata = { title: "Upgrade", robots: { index: false } };

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      <main>
        <section className="section-shell join">{children}</section>
      </main>
      <Footer />
    </>
  );
}

export default async function Page() {
  const session = readSessionCookie((await headers()).get("cookie"));
  const api = getPlatformApi();
  const guard = await guardMember(session, (s) => api.me(s));
  if (guard.kind === "redirect") redirect(guard.to);
  if (guard.kind === "unavailable") {
    return (
      <Shell>
        <h1>This page cannot be reached right now. Please try again in a minute.</h1>
      </Shell>
    );
  }

  let options: UpgradeOptions | null = null;
  try {
    options = await api.upgradeOptions(session!);
  } catch {
    options = null;
  }
  if (!options) {
    return (
      <Shell>
        <h1>The upgrade options cannot be loaded right now. Please try again in a minute.</h1>
      </Shell>
    );
  }

  const view = upgradeView(guard.me.access, options);

  if (view.kind === "paid") {
    return (
      <Shell>
        <h1>You already have full access.</h1>
        <p>
          <Link href="/member/account">See why on your Account page</Link>
        </p>
        <p>
          <Link href="/member">Open your workspace</Link>
        </p>
      </Shell>
    );
  }

  if (view.kind === "change_plan") {
    const heading =
      view.planInterval === "month"
        ? "You are on the monthly plan."
        : view.planInterval === "year"
          ? "You are on the annual plan."
          : "Your Substack subscription does not include the platform.";
    return (
      <Shell>
        <h1>{heading}</h1>
        <p>
          Full access to the platform comes with the annual plan. You change your plan in your Substack account; nothing
          is charged here.
        </p>
        {view.url ? (
          <p>
            <a className="button button-primary" href={view.url} rel="noreferrer" target="_blank">
              Change plan on Substack
            </a>
          </p>
        ) : (
          <p>Open your Substack account and choose the annual plan.</p>
        )}
        <CheckAgain />
      </Shell>
    );
  }

  return (
    <Shell>
      <h1>Get full access.</h1>
      {view.offer ? (
        <div className="promotion-offer">
          <p>
            <strong>{view.offer.badge}</strong>
          </p>
          <h2>{view.offer.headline}</h2>
          <p>{view.offer.body}</p>
          {view.offer.ends ? <p>Offer ends {view.offer.ends}.</p> : null}
        </div>
      ) : null}
      {view.url ? (
        <p>
          <a className="button button-primary" href={view.url} rel="noreferrer" target="_blank">
            Subscribe on Substack
          </a>
        </p>
      ) : null}
      <p>Subscriptions are sold and billed by Substack. When you have subscribed, come back and press Check again.</p>
      <CheckAgain />
    </Shell>
  );
}
