"use client";

import { useMemo, useState } from "react";
import { EvidenceBadge, StageBadge } from "../components/Badges";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { evidenceItems } from "../data";

const topics = ["All", ...Array.from(new Set(evidenceItems.map((item) => item.topic)))];

export default function EvidenceLibraryPage() {
  const [query, setQuery] = useState("");
  const [topic, setTopic] = useState("All");
  const [access, setAccess] = useState("All");

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return evidenceItems.filter((item) =>
      (topic === "All" || item.topic === topic) &&
      (access === "All" || item.access === access) &&
      (!q || `${item.title} ${item.summary} ${item.topic} ${item.status}`.toLowerCase().includes(q)),
    );
  }, [access, query, topic]);

  return (
    <>
      <Header />
      <main className="white-main">
        <section className="page-hero library-hero section-shell">
          <p className="section-kicker">Open evidence infrastructure</p>
          <h1>Evidence Library</h1>
          <p>Search the project’s growing collection of evidence maps, concept notes, public abstracts and clinician-facing syntheses.</p>
          <div className="library-search">
            <span aria-hidden="true">⌕</span>
            <input aria-label="Search the evidence library" onChange={(e) => setQuery(e.target.value)} placeholder="Search mechanisms, symptoms, hormones, medication or body systems…" type="search" value={query} />
          </div>
        </section>
        <section className="section-shell library-layout">
          <aside className="library-filters" aria-label="Evidence library filters">
            <h2>Filters</h2>
            <fieldset>
              <legend>Topic</legend>
              {topics.map((item) => (
                <label className="radio-line" key={item}>
                  <input checked={topic === item} name="topic" onChange={() => setTopic(item)} type="radio" />
                  {item}
                </label>
              ))}
            </fieldset>
            <fieldset>
              <legend>Access</legend>
              {["All", "Public", "Member"].map((item) => (
                <label className="radio-line" key={item}>
                  <input checked={access === item} name="access" onChange={() => setAccess(item)} type="radio" />
                  {item}
                </label>
              ))}
            </fieldset>
          </aside>
          <div className="library-results">
            <div className="results-bar"><span>Showing {items.length} entries</span><span>Recently updated</span></div>
            <div className="evidence-grid" aria-live="polite">
              {items.map((item) => (
                <article className="evidence-card" id={item.slug} key={item.slug}>
                  <div className="evidence-meta"><span>{item.access === "Public" ? "◎ Public" : "▣ Member"} · {item.type}</span><EvidenceBadge status={item.status} /></div>
                  <h2>{item.title}</h2>
                  <p>{item.summary}</p>
                  <div className="evidence-card-stage"><StageBadge stage={item.stage} /></div>
                  <div className="card-footer"><span>Updated {item.updated} · {item.topic}</span><a href={item.access === "Member" ? "https://elenaokhonko.substack.com/subscribe" : `/research-agenda`}>{item.access === "Member" ? "View membership ↗" : "Open research map →"}</a></div>
                </article>
              ))}
            </div>
            {!items.length && <div className="empty-state"><h2>No evidence entries match</h2><p>Try a broader phrase or choose all topics.</p></div>}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
