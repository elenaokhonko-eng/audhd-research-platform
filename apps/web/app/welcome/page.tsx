import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ApiError, getPlatformApi } from "@/lib/platform-api/client";
import { SESSION_COOKIE } from "@/lib/session";
import { welcomeView } from "@/lib/welcome";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { NotRecognised } from "./NotRecognised";
import { TermsStep } from "./TermsStep";

export const dynamic = "force-dynamic";
export const metadata = { title: "Welcome", robots: { index: false } };

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

export default async function Page({ searchParams }: { searchParams: Promise<{ check?: string | string[] }> }) {
  const session = (await cookies()).get(SESSION_COOKIE)?.value ?? null;
  if (!session) redirect("/join");

  let me;
  try {
    me = await getPlatformApi().me(session);
  } catch (error) {
    if (error instanceof ApiError && error.code === "unauthenticated") redirect("/join");
    throw error;
  }
  const { check } = await searchParams;
  const view = welcomeView(me, typeof check === "string" ? check : null);

  return (
    <>
      <Header />
      <main>
        {view.kind === "terms" ? (
          <TermsStep />
        ) : view.kind === "paid" ? (
          <section className="section-shell join">
            <h1>You are recognised as a paid subscriber.</h1>
            {view.includedWhilePaying ? (
              <p>Your membership is included for as long as your subscription is active.</p>
            ) : null}
            {view.grantUntil ? (
              <p>Your access is guaranteed until {dateFormat.format(new Date(view.grantUntil))}.</p>
            ) : null}
            <p>
              <Link className="button button-primary" href="/member">
                Open your workspace
              </Link>
            </p>
          </section>
        ) : (
          <section className="section-shell join">
            <h1>You are in as a free member.</h1>
            {view.checking ? (
              <p>
                We are checking your subscription. This can take a minute.{" "}
                <Link href="/welcome">Check again</Link>
              </p>
            ) : null}
            <p>
              <Link href="/upgrade">See how to upgrade</Link>
            </p>
            <NotRecognised />
          </section>
        )}
      </main>
      <Footer />
    </>
  );
}
