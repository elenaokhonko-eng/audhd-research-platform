import Link from "next/link";
import { EvidenceBadge } from "../components/Badges";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";

const resources = [
  { title: "Hormonal transitions and executive-function variability", format: "Evidence brief", audience: "GPs, psychiatrists, gynaecologists", status: "Emerging" as const, access: "Member", tone: "pink" },
  { title: "Distinguishing burnout from depressive episodes", format: "Consultation guide", audience: "Psychologists and psychiatrists", status: "Supported" as const, access: "Public", tone: "teal" },
  { title: "Sensory change during medication treatment", format: "Evidence map", audience: "Prescribers and allied health", status: "Emerging" as const, access: "Member", tone: "yellow" },
  { title: "Questions for a neuroinclusive first consultation", format: "Conversation tool", audience: "Multidisciplinary clinicians", status: "Community observation" as const, access: "Public", tone: "green" },
];

export default function ClinicianResourcesPage() {
  return (
    <>
      <Header />
      <main>
        <section className="page-hero section-shell">
          <p className="section-kicker">Evidence translation</p>
          <h1>Clinician Resources</h1>
          <p>Concise tools, consultation guides and evidence briefs designed to support neuroinclusive conversations while preserving uncertainty and source traceability.</p>
        </section>
        <section className="section-shell resource-intro">
          <div><span>01</span><h2>Readable in the consultation</h2><p>Focused formats that surface the question, the evidence level and what remains unknown.</p></div>
          <div><span>02</span><h2>Built for verification</h2><p>Every substantive claim is designed to link back to its source trail and update history.</p></div>
          <div><span>03</span><h2>Designed across languages</h2><p>Separate HTML resources are planned in English, German, French, Russian, Simplified Chinese and Korean.</p></div>
        </section>
        <section className="section section-shell">
          <div className="section-heading split-heading"><div><p className="section-kicker">Resource collection</p><h2>Current and planned briefs</h2></div><p>These launch entries describe the first evidence-translation programme. Publication links will become active as each resource completes review.</p></div>
          <div className="resource-grid">
            {resources.map((item) => (
              <article className={`resource-card tone-${item.tone}`} key={item.title}>
                <div className="resource-top"><span>{item.format}</span><EvidenceBadge status={item.status} /></div>
                <h3>{item.title}</h3>
                <dl><div><dt>For</dt><dd>{item.audience}</dd></div><div><dt>Access</dt><dd>{item.access}</dd></div><div><dt>Status</dt><dd>In development</dd></div></dl>
                <div className="card-footer"><span>English first · multilingual planned</span><Link href={item.access === "Member" ? "/member" : "/methods"}>{item.access === "Member" ? "Member preview →" : "See standards →"}</Link></div>
              </article>
            ))}
          </div>
        </section>
        <section className="section section-deep"><div className="section-shell clinician-callout"><div><p className="section-kicker light">Collaborate</p><h2>Help make evidence translation clinically useful</h2><p>Practitioners and researchers can propose review questions, identify missing sources and express interest in future advisory review.</p><Link className="button button-light" href="/about-elena-okhonko#contact">Contact the project →</Link></div><div className="callout-list"><span>01</span><p>Source suggestions</p><span>02</span><p>Clinical review</p><span>03</span><p>Translation collaboration</p></div></div></section>
      </main>
      <Footer />
    </>
  );
}
