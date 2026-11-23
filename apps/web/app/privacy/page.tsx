import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { formatDate } from "@/lib/reasons";
import { readLegal } from "@/lib/legal";

export const dynamic = "force-static";
export const metadata = { title: "Privacy notice" };

export default function Page() {
  const doc = readLegal("privacy");
  return (
    <>
      <Header />
      <main>
        <section className="section-shell">
          <article className="legal" dangerouslySetInnerHTML={{ __html: doc.html }} />
          <p>
            Version {doc.version}, in force from {formatDate(doc.effectiveFrom)}.
          </p>
        </section>
      </main>
      <Footer />
    </>
  );
}
