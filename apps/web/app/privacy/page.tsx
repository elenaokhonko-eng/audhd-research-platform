import { Footer } from "../components/Footer";
import { Header } from "../components/Header";

export const metadata = { title: "Privacy notice", robots: { index: false } };

export default function Page() {
  return (
    <>
      <Header />
      <main>
        <section className="section-shell">
          <h1>Privacy notice</h1>
          <p>This text is published before the platform opens.</p>
        </section>
      </main>
      <Footer />
    </>
  );
}
