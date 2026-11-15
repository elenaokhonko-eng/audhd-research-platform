"use client";

import { useMemo, useState } from "react";
import { EvidenceBadge, StageBadge } from "../components/Badges";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { researchQuestions } from "../data";

const topics = ["All topics", ...Array.from(new Set(researchQuestions.map((item) => item.topic)))];
const stages = ["All stages", ...Array.from(new Set(researchQuestions.map((item) => item.stage)))];

export default function ResearchAgendaPage() {
  const [topic, setTopic] = useState("All topics");
  const [stage, setStage] = useState("All stages");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return researchQuestions.filter(
      (item) =>
        (topic === "All topics" || item.topic === topic) &&
        (stage === "All stages" || item.stage === stage) &&
        (!q || `${item.title} ${item.why} ${item.topic}`.toLowerCase().includes(q)),
    );
  }, [query, stage, topic]);

  return (
    <>
      <Header />
      <main>
        <section className="page-hero section-shell">
          <p className="section-kicker">Living roadmap</p>
          <h1>Research Agenda</h1>
          <p>
            Explore the project’s evolving questions across AuDHD biology,
            development, hormones, metabolism, medication response and adaptation.
            Stages show the work in progress; evidence labels show the current
            strength of the underlying claim.
          </p>
        </section>
        <section className="section-shell agenda-layout">
          <aside className="filter-panel" aria-label="Research agenda filters">
            <div className="filter-title">
              <h2>Filter questions</h2>
              <button onClick={() => { setTopic("All topics"); setStage("All stages"); setQuery(""); }} type="button">Clear</button>
            </div>
            <label>
              Search
              <input aria-label="Search research questions" onChange={(e) => setQuery(e.target.value)} placeholder="Search questions…" type="search" value={query} />
            </label>
            <label>
              Topic
              <select onChange={(e) => setTopic(e.target.value)} value={topic}>
                {topics.map((option) => <option key={option}>{option}</option>)}
              </select>
            </label>
            <label>
              Research stage
              <select onChange={(e) => setStage(e.target.value)} value={stage}>
                {stages.map((option) => <option key={option}>{option}</option>)}
              </select>
            </label>
            <div className="filter-note">
              <strong>{filtered.length}</strong>
              <span>{filtered.length === 1 ? "question" : "questions"} shown</span>
            </div>
          </aside>
          <div className="agenda-results" aria-live="polite">
            {filtered.length ? filtered.map((item) => (
              <article className="agenda-card" id={item.slug} key={item.slug}>
                <div className="badge-row">
                  <StageBadge stage={item.stage} />
                  <EvidenceBadge status={item.status} />
                </div>
                <h2>{item.title}</h2>
                <dl>
                  <div><dt>Topic</dt><dd>{item.topic}</dd></div>
                  <div><dt>Life stage</dt><dd>{item.lifeStage}</dd></div>
                </dl>
                <div className="agenda-why">
                  <h3>Why it matters</h3>
                  <p>{item.why}</p>
                </div>
                <div className="card-footer"><span>Updated {item.updated}</span><a href={`/evidence-library?q=${encodeURIComponent(item.topic)}`}>Related evidence →</a></div>
              </article>
            )) : (
              <div className="empty-state"><h2>No questions match</h2><p>Try a broader topic or clear the filters.</p></div>
            )}
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
