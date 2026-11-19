import { identityConfig } from "@/lib/identity/config";
import { Footer } from "../../components/Footer";
import { Header } from "../../components/Header";
import { FinishSignIn } from "./FinishSignIn";

export const dynamic = "force-dynamic";
export const metadata = { robots: { index: false } };

export default function Page() {
  return (
    <>
      <Header />
      <main>
        <FinishSignIn identity={identityConfig()} />
      </main>
      <Footer />
    </>
  );
}
