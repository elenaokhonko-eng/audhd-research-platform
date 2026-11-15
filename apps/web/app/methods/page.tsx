import { Footer } from "../components/Footer";
import { Header } from "../components/Header";

const standards = [
  ["01", "Question first", "Each synthesis begins with a defined research question, population, context and scope."],
  ["02", "Traceable search", "Search terms, source classes, date ranges and exclusions are recorded for substantive evidence maps."],
  ["03", "Claims are typed", "Established evidence, support, emerging findings, hypotheses and community observations are never presented as interchangeable."],
  ["04", "Uncertainty stays visible", "Conflicting findings, missing populations and methodological limits remain part of the public summary."],
  ["05", "Living documents", "Material changes receive a new update date and a concise change-history entry."],
] as const;

export default function MethodsPage() {
  return (
    <>
      <Header />
      <main>
        <section className="page-hero methods-hero section-shell"><p className="section-kicker">Trust through method</p><h1>Methods, standards &amp; corrections</h1><p>This project is designed to make the path from question to claim inspectable. It separates source evidence, interpretation, lived observation and hypotheses so readers can see what is known—and what is not.</p></section>
        <section className="section-shell methods-layout">
          <nav className="toc" aria-label="Methods contents"><span>On this page</span><a href="#standards">Evidence standards</a><a href="#labels">Claim labels</a><a href="#community">Lived experience</a><a href="#ai">Use of AI</a><a href="#ethics">Ethics & participation</a><a href="#corrections">Corrections</a><a href="#privacy">Privacy</a></nav>
          <div className="methods-content">
            <section id="standards"><p className="section-kicker">Evidence standards</p><h2>How an evidence map is built</h2><div className="standards-list">{standards.map(([number, title, copy]) => <article key={number}><span>{number}</span><div><h3>{title}</h3><p>{copy}</p></div></article>)}</div></section>
            <section id="labels"><p className="section-kicker">Claim labels</p><h2>Evidence strength is not publication stage</h2><p>A paper can be published while its underlying claim remains preliminary. An evidence map can be in active analysis while drawing on well-established findings. For that reason, this project displays two labels: evidence status and research stage.</p><div className="method-table" role="table" aria-label="Evidence label definitions"><div role="row"><strong role="columnheader">Label</strong><strong role="columnheader">Meaning</strong></div><div role="row"><span>Established</span><span>Consistent evidence or authoritative consensus in the relevant context.</span></div><div role="row"><span>Supported</span><span>Multiple credible sources point in the same direction; meaningful limits remain.</span></div><div role="row"><span>Emerging</span><span>Early, mixed, narrow or rapidly developing evidence.</span></div><div role="row"><span>Hypothesis</span><span>A proposed explanatory model that requires testing.</span></div><div role="row"><span>Community observation</span><span>Recurring lived reports used to generate questions, not to establish causality.</span></div></div></section>
            <section id="community"><p className="section-kicker">Lived experience</p><h2>Observation generates questions; it does not replace evidence</h2><p>Lived experience can reveal patterns that formal research has not yet measured. Community reports will be grouped, moderated and clearly labelled. They may guide prioritisation or survey design, but will not be converted into clinical claims without appropriate evidence.</p></section>
            <section id="ai"><p className="section-kicker">Use of AI</p><h2>AI assists retrieval and structure—not final authority</h2><p>AI may support literature discovery, source organisation, translation drafts and retrieval from a curated collection. Substantive published claims require human review against the underlying sources. Future RAG responses will display citations, collection-update dates and a visible separation between retrieved evidence and model inference.</p></section>
            <section id="ethics"><p className="section-kicker">Ethics & participation</p><h2>Participation will match the level of research activity</h2><p>Informal audience polls, community observations and formal human-participant research are different activities. Any formal study will display its purpose, consent process, data use, governance and relevant ethics status before participation begins.</p></section>
            <section id="corrections"><p className="section-kicker">Corrections</p><h2>A public correction trail</h2><p>Material corrections will retain the original publication date, add a modification date and explain what changed. The initial correction log is empty because the library is launching now.</p><div className="empty-log"><strong>No material corrections logged</strong><span>Last checked 2 August 2026</span></div></section>
            <section id="privacy"><p className="section-kicker">Privacy</p><h2>Collect only what the project needs</h2><p>The public MVP does not collect sensitive research or health data. Substack manages newsletter subscriptions and payments under its own terms. Before member submissions or surveys launch, this page will describe the exact data collected, retention period, access controls and deletion route.</p></section>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
