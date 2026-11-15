import Link from "next/link";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { EvidenceBadge, StageBadge } from "./components/Badges";
import { researchQuestions } from "./data";

const topics = [
  {
    number: "01",
    title: "Origins & development",
    copy: "How genetic, developmental and environmental systems converge across the lifespan.",
    tone: "teal",
  },
  {
    number: "02",
    title: "Hormones & life stages",
    copy: "How endocrine transitions may alter cognition, sensory processing and medication response.",
    tone: "pink",
  },
  {
    number: "03",
    title: "Metabolism & body systems",
    copy: "How energy regulation, autonomic function and whole-body biology shape experience.",
    tone: "yellow",
  },
  {
    number: "04",
    title: "Medication response",
    copy: "Why treatment response may vary across integrated autistic and ADHD profiles.",
    tone: "blue",
  },
  {
    number: "05",
    title: "Evolution & adaptation",
    copy: "Which adaptive patterns and trade-offs may sit behind AuDHD traits.",
    tone: "green",
  },
];

const evidenceLevels = [
  ["Established", "Consistent evidence or authoritative consensus."],
  ["Supported", "Multiple credible sources; important limits remain."],
  ["Emerging", "Early, mixed or rapidly developing evidence."],
  ["Hypothesis", "A proposed explanation requiring further testing."],
  ["Community observation", "Recurring lived reports, not established evidence."],
] as const;

export default function Home() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "AuDHD Research",
    alternateName: "AuDHD Origins & Biology Research",
    url: "https://audhdneurobiology.org/",
    description:
      "An independent research project investigating the biological, developmental, hormonal, metabolic and evolutionary dimensions of co-occurring autism and ADHD.",
  };

  return (
    <>
      <Header />
      <main>
        <section className="hero section-shell" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">Independent research project</p>
            <h1 id="hero-title">
              Understanding AuDHD as an integrated biological and developmental
              system
            </h1>
            <p className="hero-lead">
              AuDHD Origins &amp; Biology Research investigates the biological,
              developmental, hormonal, metabolic and evolutionary dimensions of
              co-occurring autism and ADHD—and translates emerging evidence into
              clear, traceable research maps.
            </p>
            <div className="button-row">
              <Link className="button button-primary" href="/research-agenda">
                Explore the research <span aria-hidden="true">→</span>
              </Link>
              <a
                className="button button-secondary"
                href="https://elenaokhonko.substack.com/subscribe"
                rel="noreferrer"
                target="_blank"
              >
                Join the research membership
              </a>
            </div>
            <p className="hero-note">
              Public evidence maps stay open. Membership funds deeper reports,
              multilingual guides and future research tools.
            </p>
          </div>
          <div className="hero-art" aria-label="Living systems illustration">
            {/* Plain image avoids provider-specific runtime image optimisation. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/audhd-living-systems-hero.png"
              alt="Interwoven cellular, neural and mycelial branches forming an integrated living system"
            />
            <div className="hero-art-caption">
              <span>Living systems</span>
              <span>Interdependence · change · adaptation</span>
            </div>
          </div>
        </section>

        <section className="manifesto-band">
          <div className="section-shell manifesto-grid">
            <p className="section-kicker">The research proposition</p>
            <p>
              AuDHD is commonly split into two diagnostic categories. This project
              asks what becomes visible when it is investigated as one interacting
              developmental and biological system.
            </p>
          </div>
        </section>

        <section className="section section-shell" id="research">
          <div className="section-heading split-heading">
            <div>
              <p className="section-kicker">Research territory</p>
              <h2>What we investigate</h2>
            </div>
            <p>
              Five connected lines of inquiry, designed to evolve as the evidence
              base and community questions develop.
            </p>
          </div>
          <div className="topic-grid">
            {topics.map((topic) => (
              <article className={`topic-card tone-${topic.tone}`} key={topic.title}>
                <span className="topic-number">{topic.number}</span>
                <h3>{topic.title}</h3>
                <p>{topic.copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="section section-alt">
          <div className="section-shell">
            <div className="section-heading split-heading">
              <div>
                <p className="section-kicker">Living roadmap</p>
                <h2>Current research questions</h2>
              </div>
              <Link className="text-link" href="/research-agenda">
                View the full agenda <span aria-hidden="true">→</span>
              </Link>
            </div>
            <div className="question-grid">
              {researchQuestions.slice(0, 3).map((item) => (
                <article className="question-card" key={item.slug}>
                  <div className="badge-row">
                    <StageBadge stage={item.stage} />
                    <EvidenceBadge status={item.status} />
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.why}</p>
                  <div className="card-footer">
                    <span>{item.topic}</span>
                    <Link href={`/research-agenda#${item.slug}`}>
                      View question <span aria-hidden="true">→</span>
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section section-shell">
          <div className="section-heading centered-heading">
            <p className="section-kicker">Evidence without false certainty</p>
            <h2>Every claim shows what kind of knowledge it is</h2>
            <p>
              Evidence status and research stage are separate. A published piece
              can still describe an emerging finding or a hypothesis.
            </p>
          </div>
          <div className="evidence-legend">
            {evidenceLevels.map(([label, copy]) => (
              <div className="legend-item" key={label}>
                <EvidenceBadge status={label} />
                <p>{copy}</p>
              </div>
            ))}
          </div>
          <div className="center-action">
            <Link className="text-link" href="/methods">
              Read our evidence standards <span aria-hidden="true">→</span>
            </Link>
          </div>
        </section>

        <section className="section section-deep">
          <div className="section-shell clinician-callout">
            <div>
              <p className="section-kicker light">For clinicians</p>
              <h2>Evidence translation for neuroinclusive care</h2>
              <p>
                Concise briefs and consultation tools that preserve uncertainty,
                make mechanisms traceable and keep lived experience in view.
              </p>
              <Link className="button button-light" href="/clinician-resources">
                Explore clinician resources <span aria-hidden="true">→</span>
              </Link>
            </div>
            <div className="callout-list" aria-label="Clinician resource principles">
              <span>01</span><p>Clear evidence status</p>
              <span>02</span><p>Full source trails</p>
              <span>03</span><p>Multilingual formats</p>
              <span>04</span><p>Designed for conversation</p>
            </div>
          </div>
        </section>

        <section className="section section-shell membership-section" id="membership">
          <div className="membership-panel">
            <div>
              <p className="section-kicker">Fund independent inquiry</p>
              <h2>Join the research membership</h2>
              <p>
                Support evidence mapping outside institutional silos and receive
                deeper research reports, practical guides, member briefings and
                early access to participatory research tools.
              </p>
            </div>
            <div className="membership-action">
              <a
                className="button button-primary"
                href="https://elenaokhonko.substack.com/subscribe"
                rel="noreferrer"
                target="_blank"
              >
                View membership on Substack <span aria-hidden="true">↗</span>
              </a>
              <Link className="text-link" href="/member">
                Preview the member workspace
              </Link>
            </div>
          </div>
        </section>
      </main>
      <Footer />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
    </>
  );
}
