"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";

const suggestions = ["What evidence connects hormonal change with ADHD symptom variation?", "What is known about AuDHD and autonomic symptoms?", "Compare the evidence status of two proposed mechanisms."];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [submitted, setSubmitted] = useState(false);
  function submit(event: FormEvent) { event.preventDefault(); if (question.trim()) setSubmitted(true); }
  return (
    <><Header /><main><section className="ask-hero section-shell"><p className="section-kicker">Phase 3 preview</p><h1>Ask AuDHD Research</h1><p>The future cited research assistant will search a curated evidence collection, show its sources and distinguish retrieval from inference.</p><form className="ask-box" onSubmit={submit}><label htmlFor="research-question">What would you like to explore?</label><textarea id="research-question" onChange={(e) => { setQuestion(e.target.value); setSubmitted(false); }} placeholder="Ask about AuDHD biology, a mechanism, symptom pattern or research question…" rows={5} value={question} /><div className="ask-actions"><span>Curated evidence only · source cards planned</span><button className="button button-primary" type="submit">Preview search →</button></div></form>{submitted && <div className="ask-response" aria-live="polite"><p className="section-kicker">Preview response</p><h2>This question is ready for the research pipeline</h2><p>The cited retrieval engine is not connected in Phase 1, so the site will not generate an uncited health answer. For now, you can search the public library or see how this topic fits the research agenda.</p><div className="button-row"><Link className="button button-primary" href={`/evidence-library`}>Search the evidence library</Link><Link className="button button-secondary" href="/research-agenda">Explore the research agenda</Link></div></div>}<div className="suggested-grid"><p className="section-kicker">Suggested inquiries</p><div>{suggestions.map((item, index) => <button key={item} onClick={() => { setQuestion(item); setSubmitted(false); }} type="button"><span>0{index + 1}</span>{item}</button>)}</div></div></section></main><Footer /></>
  );
}
