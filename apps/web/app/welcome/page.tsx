import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { getPlatformApi } from "@/lib/platform-api/client";
import { readSessionCookie } from "@/lib/session";
import { welcomeState } from "@/lib/welcome";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { WelcomeBody } from "./WelcomeBody";

export const dynamic = "force-dynamic";
export const metadata = { title: "Welcome", robots: { index: false } };

export default async function Page({ searchParams }: { searchParams: Promise<{ check?: string | string[] }> }) {
  // The same parser as the API routes, so a page and a route never disagree about which cookie is the session.
  const session = readSessionCookie((await headers()).get("cookie"));
  if (!session) redirect("/join");

  const { check } = await searchParams;
  const state = await welcomeState(() => getPlatformApi().me(session), typeof check === "string" ? check : null);
  if (state.kind === "signin") redirect("/join");

  return (
    <>
      <Header />
      <main>
        <WelcomeBody view={state} />
      </main>
      <Footer />
    </>
  );
}
