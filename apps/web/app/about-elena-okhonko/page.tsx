import Link from "next/link";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";

export default function AboutPage() {
  const jsonLd = { "@context": "https://schema.org", "@type": "ProfilePage", mainEntity: { "@type": "Person", name: "Elena Okhonko", jobTitle: "Founder and Lead Researcher", affiliation: { "@type": "Project", name: "AuDHD Origins & Biology Research" }, knowsLanguage: ["English", "Russian", "German", "French", "Mandarin Chinese", "Korean"] } };
  return (
    <>
      <Header />
      <main>
        <section className="about-hero section-shell"><div><p className="section-kicker">Founder &amp; lead researcher</p><h1>Elena Okhonko</h1><p className="about-intro">Building a research project at the intersection of lived experience, complex systems, evidence translation and applied AI.</p></div><div className="portrait-placeholder" aria-label="Portrait space"><span>EO</span><small>Founder portrait</small></div></section>
        <section className="section-shell about-layout"><aside><p>Singapore-based independent research project</p><dl><div><dt>Role</dt><dd>Founder &amp; lead researcher</dd></div><div><dt>Languages</dt><dd>English, Russian, German, French, Mandarin and Korean</dd></div><div><dt>Focus</dt><dd>AuDHD biology, development, hormones, metabolism and evidence systems</dd></div></dl></aside><div className="about-story"><section><p className="section-kicker">Why this project exists</p><h2>Important questions are falling between disciplines</h2><p>Research on autism, ADHD, hormonal transitions, metabolism, autonomic function and lived adaptation is frequently produced in separate fields. AuDHD Origins &amp; Biology Research was created to map the interfaces between them and make the evidence traceable to the people who need it.</p></section><section><p className="section-kicker">Perspective</p><h2>Lived experience and systems thinking</h2><p>Elena combines lived AuDHD experience with a professional background in complex transformation programmes, technology, AI and data science. Her role is to define research questions, build evidence-mapping systems, translate findings and develop collaborations—not to imply institutional authority the project has not earned.</p></section><section><p className="section-kicker">Research role</p><h2>Independent, transparent and collaboration-ready</h2><p>The project begins as an independent research initiative. Formal studies, advisory review and research partnerships will be described precisely as they are established. Methods, funding relationships, AI use, conflicts and corrections will remain visible.</p></section><section id="contact" className="contact-panel"><p className="section-kicker">Contact & collaboration</p><h2>Propose a source, review question or collaboration</h2><p>For now, the most reliable contact route is through Elena’s publication. A dedicated <strong>@audhdresearch.org</strong> address will be added after the domain is configured.</p><div className="button-row"><a className="button button-primary" href="https://elenaokhonko.substack.com/" rel="noreferrer" target="_blank">Contact via Substack ↗</a><Link className="button button-secondary" href="/methods">Review the methods</Link></div></section></div></section>
      </main>
      <Footer />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
    </>
  );
}
