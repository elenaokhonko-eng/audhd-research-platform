import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { identityConfig } from "@/lib/identity/config";
import { getPlatformApi } from "@/lib/platform-api/client";
import type { Campaign } from "@/lib/platform-api/types";
import { readSessionCookie } from "@/lib/session";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { JoinScreen } from "./JoinScreen";

const closedCampaign = (slug: string | null): Campaign => ({
  slug,
  audience: "public",
  state: "closed",
  copy: { headline: "Opening soon", body: "Sign-in opens soon. Come back later.", cta: "" },
});

export async function JoinPage({ slug }: { slug: string | null }) {
  const api = getPlatformApi();
  const session = readSessionCookie((await headers()).get("cookie")); // the same parser as the API routes

  let signedIn = false;
  if (session) {
    try {
      await api.me(session);
      signedIn = true;
    } catch {
      // Unauthenticated or unavailable: show the join screen; never loop with /welcome.
    }
  }
  if (signedIn) redirect("/welcome");

  let campaign: Campaign;
  try {
    campaign = await api.campaign(slug);
  } catch {
    campaign = closedCampaign(slug);
  }

  return (
    <>
      <Header />
      <main>
        <JoinScreen
          campaign={campaign}
          identity={identityConfig()}
          senderHint={process.env.SIGNIN_SENDER_HINT || null}
          siteOrigin={process.env.SITE_ORIGIN ?? ""}
          slug={slug}
        />
      </main>
      <Footer />
    </>
  );
}
