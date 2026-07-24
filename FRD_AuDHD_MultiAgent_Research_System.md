# AuDHD Phenotype Research Multi-Agent System
## Functional Requirements Document (FRD) v1.0

**Document Version:** 1.0  
**Date:** 2026-07-23  
**Classification:** Research Infrastructure Specification  
**Domain:** Neurodivergence Research (AuDHD Phenotypes)  
**Orchestration Framework:** CrewAI Multi-Agent Framework  
**Standards Compliance:** MCP v1.17, ISO 27001 (Data Handling), COPE Guidelines

---

## 1. EXECUTIVE SUMMARY

This document specifies a multi-agent research pipeline built entirely on the **CrewAI Multi-Agent Framework** to conduct rigorous scientific investigation into AuDHD (comorbid Autism Spectrum Disorder + ADHD) phenotypes. The system transforms raw researcher hypotheses into publication-ready scientific papers and accessible Substack articles through a 12-agent hierarchical and sequential network.

Following the core philosophy of **intent-driven orchestration**, this system leverages CrewAI's declarative, configuration-driven architecture (separating agents/tasks configs in YAML from code in Python). It enforces **deterministic execution paths** using CrewAI sequential and hierarchical processes, integrates **Human-in-the-Loop (HITL) checkpoints** at critical decision gates, and implements **multi-tier critic validation** before any output is finalized.

---

## 2. SYSTEM ARCHITECTURE OVERVIEW

### 2.1 Orchestration Pattern: CrewAI Process Flow

The system implements a hybrid process flow utilizing CrewAI's native execution engines:
1. **Sequential Process (`Process.sequential`)**: Governs the macro phases of the research pipeline, ensuring that the outputs of preceding tasks are seamlessly passed as context to the next agent.
2. **Hierarchical Process (`Process.hierarchical`)**: Governs the parallel research and Manager-Critic phase, where a manager agent dynamically delegates sub-tasks to a pool of Junior Researchers and coordinates with the Critic before finalizing the synthesis.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CREW MANAGER (CrewAI Orchestrator)               │
│                Memory + Context Management + Human-in-Loop              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   ┌────▼────┐                ┌─────▼─────┐              ┌──────▼──────┐
   │ PHASE 1 │                │  PHASE 2  │              │   PHASE 3   │
   │Hypothesis│               │ Research  │              │ Publication │
   │Formalize │               │ Execution │              │  Pipeline   │
   └────┬────┘                └─────┬─────┘              └──────┬──────┘
        │                           │                           │
   ┌────▼────┐                ┌─────▼─────┐              ┌──────▼──────┐
   │ Analyst │                │  Junior   │              │  Substack   │
   │  Agent  │───passes to───▶│ Research  │──consolidate▶│   Writer    │
   │ (A01)   │   formalized   │  Agents   │    to        │   (A08)     │
   │         │   hypothesis   │  (A03)    │              │             │
   └─────────┘                └─────┬─────┘              └─────────────┘
                                    │
                              ┌─────▼─────┐
                              │  Research │
                              │  Manager  │
                              │  (A04)    │
                              └─────┬─────┘
                                    │
                              ┌─────▼─────┐
                              │ Grounding │
                              │ Verifier  │
                              │  (A13)    │
                              └─────┬─────┘
                                    │ (strictly certified)
                              ┌─────▼─────┐
                              │  Research │
                              │  Critic   │
                              │  (A05)    │
                              └─────┬─────┘
                                    │ (iterative loop)
                              ┌─────▼─────┐
                              │  Research │
                              │  Editor   │
                              │  (A06)    │
                              └─────┬─────┘
                                    │
                              ┌─────▼─────┐
                              │  Paper    │
                              │  Critic   │
                              │  (A07)    │
                              └─────┬─────┘
                                    │ (pass/fail gate)
                              ┌─────▼─────┐
                              │  Visual   │
                              │  Graphics │
                              │  (A09)    │
                              └───────────┘
```

### 2.2 State, Memory, and Context Persistence

Instead of a traditional state graph, CrewAI maintains state through:
- **Crew Short-Term Memory**: Holds contextual execution states and inter-agent outputs during a run.
- **Crew Long-Term Memory**: Stores historical outcomes, allowing agents to learn from past executions and critics' feedback.
- **Task Context Passing**: Tasks are explicitly configured with `context=[task_a, task_b]` to carry over detailed JSON payloads and data metrics between stages.
- **Custom CrewAI Checkpoints**: Preserves states and facilitates resuming/time-travel debugging via local sqlite/JSON storage.

---

### 2.3 Communication Protocol: MCP (Model Context Protocol)

All tools are standard Python functions or CrewAI `Tool` classes registered within an MCP v1.17 framework. The agents query these tools dynamically:

| MCP Server / Tool | Purpose | Primary Agents |
|---|---|---|
| `arxiv-mcp` | Academic preprint searches | Junior Research Agents (A03) |
| `pubmed-mcp` | Clinical & biomedical database queries | Junior Research Agents (A03) |
| `semantic-scholar-mcp` | Citation metrics and graph exploration | Junior Research Agents (A03) |
| `google-scholar-mcp` | General literature review | Junior Research Agents (A03) |
| `crossref-mcp` | DOI verification and bibliographic fetch | All Research Agents |
| `zotero-mcp` | Workspace library & bibliography storage | Research Editor (A06) |
| `substack-mcp` | Automated drafting & queuing on Substack | Scheduling Agent (A11) |
| `email-mcp` | Deliver paper to paid list via SMTP/SendGrid | Email Agent (A12) |
| `filesystem-mcp` | Structured reading/writing of .md, .docx, .pdf | Research Editor (A06) |
| `graphics-mcp` | DALL-E/Midjourney/Matplotlib API triggers | Visual Graphics (A09) |
| `notion-mcp` | Updates CRM status, schedule dates, backlinks | Scheduling Agent (A11) |

---

## 3. FUNCTIONAL REQUIREMENTS BY AGENT

### 3.1 AGENT-01: Hypothesis Analyst

**Role:** Scientific Hypothesis Formalization Specialist  
**Orchestration Pattern:** Sequential Task (Human-in-the-Loop)  
**Model Tier:** Premium Reasoning (Claude Opus 4.8 / Gemini 2.5 Pro)

#### 3.1.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A01-001 | Accept raw hypothesis text from researcher via UI/API | P0 | JSON payload with `raw_hypothesis` field processed within 5s |
| FR-A01-002 | Decompose raw hypothesis into conceptual, operational, and statistical components per Hypothesis Formalization Framework (Klahr & Simon dual-search model) | P0 | Output contains: conceptual hypothesis, operationalized variables, proposed statistical model, proxy definitions |
| FR-A01-003 | Generate clarifying questions using Socratic elicitation protocol | P0 | 3-7 questions generated; each question targets a specific ambiguity in the raw hypothesis |
| FR-A01-004 | Support multi-turn dialogue for hypothesis refinement | P0 | State persists across turns; analyst references previous answers |
| FR-A01-005 | Output formalized hypothesis in structured JSON schema | P0 | Valid against `FormalizedHypothesisDocument` Schema |
| FR-A01-006 | Include falsifiability assessment and null hypothesis formulation | P1 | Explicit H0 and H1 stated; testability criteria defined |
| FR-A01-007 | Flag ethical considerations specific to neurodivergent population research | P1 | Ethics checklist: consent, vulnerability, stigma risk, benefit/risk ratio |
| FR-A01-008 | Generate preliminary literature gap analysis | P1 | Identifies 3-5 known gaps the hypothesis addresses |

#### 3.1.2 Input/Output Specification

- **Input Context**: `RawHypothesisPayload`
- **Output Target**: `FormalizedHypothesisDocument`
- **Human Gate**: Required — `human_input=True` enabled on the hypothesis-validation task.

---

### 3.2 AGENT-02: Research Team Head (Research Director)

**Role:** Research Strategy & Task Decomposition Lead  
**Orchestration Pattern:** Hierarchical Process Planner  
**Model Tier:** Premium Reasoning (Claude Opus 4.8 / Gemini 2.5 Pro)

#### 3.2.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A02-001 | Accept formalized hypothesis from Analyst Agent | P0 | Validates schema compliance before planning |
| FR-A02-002 | Decompose hypothesis into 3-8 parallel research tasks | P0 | Each task has: scope, search queries, target sources, expected outputs |
| FR-A02-003 | Apply decision tree for source allocation: PubMed (clinical), arXiv (preprints), Semantic Scholar (citation graphs), Google Scholar (broad), PsycINFO (psychology) | P0 | Each task assigned primary and secondary source repositories |
| FR-A02-004 | Identify research task dependencies and mark independent vs. sequential tasks | P1 | Task sequence and contexts mapped inside Crew configurations |
| FR-A02-005 | Estimate token budget and compute allocation per task | P1 | Cost estimate provided; budget alerts configured |
| FR-A02-006 | Assign tasks to available Junior Research Agent pool | P0 | Round-robin or load-balanced distribution |
| FR-A02-007 | Monitor task progress and handle agent failures with retry logic | P0 | Max 3 retries per task; escalation to human after failure |

---

### 3.3 AGENT-03: Junior Research Agents (Pool)

**Role:** Parallel Literature Review & Data Extraction Workers  
**Orchestration Pattern:** Concurrent/Parallel (mapped via CrewAI)  
**Model Tier:** Standard (Claude Sonnet 4.6 / Gemini 2.0 Flash) — cost-optimized for volume  
**Quantity:** 3-8 instances running in parallel

#### 3.3.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A03-001 | Execute assigned search queries across designated academic repositories | P0 | Returns ≥10 relevant papers per task; relevance score ≥0.7 |
| FR-A03-002 | Download and parse full-text PDFs where available | P0 | PDF text extraction with section parsing (abstract, methods, results, discussion) |
| FR-A03-003 | Extract structured data: sample size, methodology, key findings, effect sizes, confidence intervals, p-values | P0 | Data extraction follows PRISMA-inspired schema |
| FR-A03-004 | Identify and catalog all citations from each paper | P0 | Citation graph node created per paper; backward citations tracked |
| FR-A03-005 | Identify key researchers in the domain with h-index ≥20 | P1 | Researcher profile includes: name, affiliation, h-index, top 5 papers, contact email (if public) |
| FR-A03-006 | Flag papers for quality: peer-reviewed status, journal impact factor, preprint vs. published | P1 | Quality tier assigned: Tier-1 (high-impact peer-reviewed), Tier-2 (peer-reviewed), Tier-3 (preprint/other) |
| FR-A03-007 | Extract contradictory findings and note methodological limitations | P1 | Limitations section extracted per paper; contradictions flagged with context |
| FR-A03-008 | Generate per-paper summary in structured format | P0 | Output: `PaperExtraction` schema compliant |
| FR-A03-009 | Handle paywalled content via Open Access alternatives (Unpaywall, Sci-Hub fallback — legal compliance check) | P2 | OA version prioritized; legal compliance verified |

#### 3.3.2 Parallel Execution Constraints

- **Max concurrency:** 8 agents
- **Rate limiting:** Respects API quotas (PubMed: 3 req/s, Semantic Scholar: 100 req/5min)
- **Timeout per task:** 10 minutes
- **Retry policy:** Exponential backoff, max 3 attempts

---

### 3.4 AGENT-04: Research Manager

**Role:** Research Synthesis & Consolidation Lead  
**Orchestration Pattern:** Sequential Synthesis  
**Model Tier:** Premium Reasoning (Claude Opus 4.8)

#### 3.4.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A04-001 | Ingest all `PaperExtraction` outputs from Junior Research Agents | P0 | Validates schema for each input; flags malformed data |
| FR-A04-002 | Deduplicate papers across parallel tasks | P0 | DOI-based deduplication; duplicate detection rate ≥99% |
| FR-A04-003 | Synthesize findings into thematic clusters | P0 | 3-7 thematic clusters identified; each with supporting paper IDs |
| FR-A04-004 | Resolve contradictions between studies with evidence weighting | P0 | Contradiction matrix generated; resolution rationale documented |
| FR-A04-005 | Calculate aggregate effect sizes where meta-analysis is possible | P1 | Forest plot data generated; heterogeneity (I²) calculated |
| FR-A04-006 | Identify research gaps remaining after literature review | P0 | Gap analysis maps to original hypothesis; identifies underexplored areas |
| FR-A04-007 | Generate consolidated research report in structured format | P0 | Output: `ConsolidatedResearchReport` schema compliant |
| FR-A04-008 | Pass consolidated report to Research Critic Agent | P0 | Handoff includes full context + original hypothesis |

---

### 3.5 AGENT-05: Research Review Critic Agent

**Role:** Adversarial Research Validation & Quality Assurance  
**Orchestration Pattern:** Iterative Challenge Loop  
**Model Tier:** Premium Reasoning with Extended Thinking (Claude Opus 4.8 Extended Thinking)

#### 3.5.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A05-001 | Evaluate consolidated research against formalized hypothesis | P0 | Coverage score: % of hypothesis components addressed by evidence |
| FR-A05-002 | Challenge statistical validity of cited studies | P0 | Flags: underpowered studies (n<30), p-hacking indicators, questionable research practices |
| FR-A05-003 | Verify citation accuracy: check that cited claims exist in original papers | P0 | Spot-check 20% of citations; accuracy rate ≥95% |
| FR-A05-004 | Assess publication bias and file-drawer problem risk | P1 | Funnel plot analysis attempted; Egger's test where data sufficient |
| FR-A05-005 | Challenge assumptions and unstated premises in the research synthesis | P0 | ≥5 critical questions raised per synthesis |
| FR-A05-006 | Evaluate generalizability to AuDHD population specifically | P0 | Flags studies using ASD-only or ADHD-only samples vs. comorbid samples |
| FR-A05-007 | Score overall research quality on 5-dimensional rubric (see SKILL.md) | P0 | Scorecard generated: Methodology, Evidence Quality, Logic, Completeness, Novelty |
| FR-A05-008 | Provide actionable feedback for improvement or approve for next phase | P0 | If score < threshold: detailed feedback + return to Manager; If score ≥ threshold: pass to Editor |
| FR-A05-009 | Maintain critique history across iterations | P1 | Versioned feedback log; regression check on previous issues |

#### 3.5.2 Critic Evaluation Rubric (5-Dimensional)

| Dimension | Weight | Criteria |
|---|---|---|
| Methodological Rigor | 25% | Study designs appropriate? Controls adequate? Confounders addressed? |
| Evidence Quality | 25% | Peer-reviewed ratio? Impact factor distribution? Replication status? |
| Logical Coherence | 20% | Arguments valid? Fallacies absent? Conclusions follow from evidence? |
| Hypothesis Coverage | 20% | All H1 components addressed? Null hypothesis considered? |
| Scientific Novelty | 10% | New insights generated? Literature gaps filled? |

**Pass Threshold:** ≥80% weighted score  
**Max Iterations:** 3 critic loops before mandatory human review (`human_input=True` escalation CP-02)

---

### 3.6 AGENT-06: Research Editor Agent

**Role:** Multi-Format Scientific Document Producer  
**Orchestration Pattern:** Sequential Task Pipeline  
**Model Tier:** Standard (Claude Sonnet 4.6 / GPT-5.4)

#### 3.6.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A06-001 | Ingest approved consolidated research + formalized hypothesis | P0 | Validates input completeness before production |
| FR-A06-002 | Generate research paper in Markdown format | P0 | Structure: Abstract, Introduction, Literature Review, Methods (review protocol), Results, Discussion, Conclusion, References |
| FR-A06-003 | Generate research paper in DOCX format | P0 | APA 7th edition formatting; styles applied; table of contents |
| FR-A06-004 | Generate research paper in PDF format | P0 | LaTeX-compiled PDF; proper typography; embedded fonts |
| FR-A06-005 | Generate all data visualizations as code (Python matplotlib/plotly) | P0 | Charts reproducible from source data; embedded in all formats |
| FR-A06-006 | Format references in APA 7th edition | P0 | All citations match Crossref/DOI metadata; hanging indents correct |
| FR-A06-007 | Include appendix with full extraction tables | P1 | PRISMA-style flow diagram; extraction table per paper |
| FR-A06-008 | Pass completed paper to Research Paper Critic Agent | P0 | All three formats generated before handoff |

---

### 3.7 AGENT-07: Research Paper Critic Agent

**Role:** Scientific Publication Standards Validator  
**Orchestration Pattern:** Gatekeeper Task Validation  
**Model Tier:** Premium (Claude Opus 4.8 / Gemini 2.5 Pro)

#### 3.7.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A07-001 | Validate paper structure against scientific standards (IMRaD +) | P0 | All required sections present; word counts within norms |
| FR-A07-002 | Validate reference formatting and completeness | P0 | All in-text citations have bibliography entries; DOI present for post-2000 papers |
| FR-A07-003 | Validate data presentation: tables readable, figures labeled, statistical notation correct | P0 | APA style compliance; alt-text for accessibility |
| FR-A07-004 | Validate logical flow: each section connects to next; arguments build | P0 | Transition quality scored; logical gap analysis performed |
| FR-A07-005 | Validate that all claims are evidence-backed with proper attribution | P0 | Unsourced claims flagged; citation density check |
| FR-A07-006 | Validate graphics are data-based (not illustrative) for research paper | P0 | All figures derived from extracted data; source data referenced |
| FR-A07-007 | Generate validation report with pass/fail per category | P0 | Report structured per validation checklist |
| FR-A07-008 | Gate: only pass to Substack Writer if all P0 criteria pass | P0 | Hard gate; no exceptions |

---

### 3.8 AGENT-08: Substack Creative Writing Agent

**Role:** Science Communication & Creative Content Writer  
**Orchestration Pattern:** Sequential Task with Visual Collaboration  
**Model Tier:** Premium Creative (Claude Sonnet 4.6 Creative / GPT-5.4 with high temperature)

#### 3.8.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A08-001 | Ingest validated research paper and extract key findings | P0 | Core 3-5 takeaways identified for article focus |
| FR-A08-002 | Write article in accessible but scientifically accurate language | P0 | Flesch-Kincaid readability: 50-70 (10th-12th grade); technical terms explained |
| FR-A08-003 | Maintain scientific integrity: no oversimplification that distorts findings | P0 | Accuracy check: all claims traceable to research paper |
| FR-A08-004 | Write for AuDHD audience: neurodivergent-affirming language, strength-based framing | P0 | Language audit: pathologizing terms flagged and replaced |
| FR-A08-005 | Include "TL;DR" summary for ADHD readers (short attention span accommodation) | P0 | TL;DR ≤150 words; bullet format; positioned at top |
| FR-A08-006 | Include "Deep Dive" sections for autistic detail-oriented readers | P0 | Expandable/collapsible sections with full methodological detail |
| FR-A08-007 | Generate compelling headline and subheadings | P0 | Headline score ≥70 on CoSchedule Headline Analyzer equivalent |
| FR-A08-008 | Include personal narrative hooks where appropriate (with researcher approval) | P1 | First-person framing optional; flagged for human review |
| FR-A08-009 | Collaborate with Visual Graphics Agent for article illustrations | P0 | Image placeholders specified; alt-text provided |
| FR-A08-010 | Output article in Substack-compatible Markdown | P0 | Valid Substack Markdown; embed syntax correct |

---

### 3.9 AGENT-09: Visual Graphics Agent

**Role:** Multi-Modal Graphics & Data Visualization Producer  
**Orchestration Pattern:** Service Agent (called by Editor and Writer)  
**Model Tier:** Visual LLM API (DALL-E 4 / Midjourney API v7 / Stable Diffusion 3.5 / Gemini 2.0 Flash Image)

#### 3.9.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A09-001 | Generate data visualizations for research paper: charts, graphs, forest plots, PRISMA diagrams | P0 | All charts reproducible from CSV data; Python source code provided |
| FR-A09-002 | Generate creative illustrations for Substack articles matching auDHD phenotype design theme | P0 | Style guide compliance (see Design System below) |
| FR-A09-003 | Generate infographics summarizing key research findings | P1 | Square format (1200x1200) for social sharing |
| FR-A09-004 | Generate header images for Substack articles (1100x200 per user preference) | P0 | Dimensions exact; text overlay readable; brand consistent |
| FR-A09-005 | Provide alt-text for all images for accessibility | P0 | Descriptive alt-text ≤125 characters; data viz includes extended description |
| FR-A09-006 | Maintain asset library with versioned images | P1 | File naming: `{article_id}_{type}_{version}.{ext}` |

#### 3.9.2 Design System: AuDHD Phenotype Theme

| Element | Specification |
|---|---|
| Color Palette | Earth tones: forest green (#2D5A3D), warm terracotta (#C4785A), deep ocean (#1A3A52), cream (#F5F1E8), gold accent (#D4A843) |
| Typography | Headings: Serif (Crimson Pro); Body: Sans-serif (Inter); Neurodivergent-friendly: dyslexia-friendly alternatives available |
| Imagery Style | Nature-biophilic: trees, roots, neural networks visualized as mycelium, earth energy connections, abstract brain-nature fusion |
| Accessibility | WCAG 2.1 AA minimum; contrast ratios ≥4.5:1; no flashing elements |
| Mood | Grounding, authentic, slightly mystical but scientifically grounded |

---

### 3.10 AGENT-10: Substack Critic Agent

**Role:** Audience-Fit & Content Quality Validator  
**Orchestration Pattern:** Gatekeeper Task Validation  
**Model Tier:** Standard (Claude Sonnet 4.6)

#### 3.10.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A10-001 | Validate article against Substack best practices: length, formatting, links, images | P0 | Checklist: optimal length (1500-3000 words), ≤3 images per scroll, external links functional |
| FR-A10-002 | Validate audience fit for AuDHD readers: tone, pacing, cognitive load | P0 | Cognitive load score assessed; paragraph length ≤4 sentences recommended |
| FR-A10-003 | Validate TL;DR section is genuinely skimmable | P0 | TL;DR passes "10-second test" — key message grasped in 10s |
| FR-A10-004 | Validate Deep Dive sections satisfy detail-oriented readers | P0 | Technical depth matches research paper; no accuracy loss |
| FR-A10-005 | Validate images are appropriate, on-theme, and properly licensed | P0 | All images have provenance; AI-generated images labeled per platform policy |
| FR-A10-006 | Validate data references in article match research paper | P0 | Spot-check 100% of numeric claims against source |
| FR-A10-007 | Score article on engagement predictors: headline, hook, CTA, shareability | P1 | Predicted engagement score provided |
| FR-A10-008 | Gate: approve for scheduling or return to writer with feedback | P0 | Hard gate with detailed feedback report |

---

### 3.11 AGENT-11: Substack Scheduling & Posting Agent

**Role:** Content Queue Manager & Publisher  
**Orchestration Pattern:** Scheduled Task Automation  
**Model Tier:** Lightweight (Claude Haiku 4.5 / Gemini 2.0 Nano)

#### 3.11.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A11-001 | Maintain publishing backlog/queue in Notion database | P0 | Database schema: Title, Status (Draft/Scheduled/Published), Publish Date, Topic, Article ID |
| FR-A11-002 | Accept approved article from Substack Critic | P0 | Validates article approval status before queuing |
| FR-A11-003 | Schedule posts at optimal times (configurable: default Tue/Thu 8am SGT) | P0 | Timezone-aware scheduling; conflict detection |
| FR-A11-004 | Publish immediately when "PUBLISH NOW" flag set | P0 | Publishes within 60 seconds of flag activation |
| FR-A11-005 | Handle image uploads and embedding | P0 | All article images uploaded to Substack CDN; embed URLs resolved |
| FR-A11-006 | Update Notion status on publish completion | P0 | Status: Draft → Scheduled → Published with timestamp |
| FR-A11-007 | Generate publishing report: URL, publish time, word count, estimated read time | P1 | Report delivered to researcher via email/notification |
| FR-A11-008 | Support cross-posting to LinkedIn, X, Medium (future) | P2 | Narrareach API integration for multi-platform distribution |

---

### 3.12 AGENT-12: Email Distribution Agent

**Role:** Paid Subscriber Research Paper Distributor  
**Orchestration Pattern:** Triggered Task Automation  
**Model Tier:** Lightweight (Claude Haiku 4.5)

#### 3.12.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A12-001 | Trigger on research paper completion (parallel to Substack pipeline) | P0 | Triggered by Paper Critic approval event |
| FR-A12-002 | Retrieve paid subscriber list from Substack | P0 | API integration; respects GDPR/privacy settings |
| FR-A12-003 | Compose email with research paper abstract + download links (.md, .doc, .pdf) | P0 | Email template: personalized greeting, abstract, key findings, download CTA |
| FR-A12-004 | Attach or link to all three paper formats | P0 | Files hosted on secure CDN; signed URLs with expiry |
| FR-A12-005 | Send email with deliverability optimization | P0 | SPF/DKIM/DMARC compliant; spam score <3 |
| FR-A12-006 | Track opens, clicks, downloads | P1 | Analytics dashboard: open rate, CTR, download rate per format |
| FR-A12-007 | Respect unsubscribe requests immediately | P0 | Real-time suppression list compliance |

---

### 3.13 AGENT-13: Hallucination & Grounding Verifier

**Role:** Factual Grounding & Hallucination Elimination Specialist  
**Orchestration Pattern:** Sequential Guardrail  
**Model Tier:** Premium Reasoning (Claude Opus 4.8 / Claude Sonnet 4.6 with `temperature=0.0`)

#### 3.13.1 Functional Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-A13-001 | Ingest synthesized reports, final drafts, or creative articles | P0 | Supports auditing across Phase 2, Phase 3, and Phase 4 outputs |
| FR-A13-002 | Execute Citation Existence Checks on all DOIs | P0 | Verifies every referenced paper DOI exists in Semantic Scholar/Crossref (raises FAIL on fake DOIs) |
| FR-A13-003 | Enforce NLI Textual Grounding on all synthesis arguments | P0 | Cross-references generated claims against original paper extracts (`PaperExtraction`) to guarantee entailment |
| FR-A13-004 | Conduct Quotation Exactness auditing on direct quotes | P0 | Direct quotes must be exact character matches of parsed full-text source snips |
| FR-A13-005 | Enforce Numerical Consistency on all statistics and coefficients | P0 | Guarantees all sample sizes (N), p-values, standard deviations, and effect sizes perfectly match source papers with zero rounding drifts |
| FR-A13-006 | Generate detailed Factual Grounding Audit Reports | P0 | Lists verified DOIs, audited quotation accuracy scores, and numerical maps |
| FR-A13-007 | Reject outputs that fail grounding to synthesis loops with explicit mismatch reasons | P0 | Triggers a retry loopback if any discrepancy, drift, or fabrication is identified |
| FR-A13-008 | Emit safety Grounding Certification on complete validation success | P0 | Validated drafts receive a "PASS" and the verifier's safety seal |


---

## 4. NON-FUNCTIONAL REQUIREMENTS

### 4.1 Performance

| ID | Requirement | Target |
|---|---|---|
| NFR-001 | End-to-end pipeline latency (hypothesis → published article) | ≤48 hours for standard research; ≤72 hours for complex meta-analyses |
| NFR-002 | Junior Research Agent parallel task completion | ≤15 minutes per task (10 papers) |
| NFR-003 | Critic agent response time | ≤5 minutes per review cycle |
| NFR-004 | Document generation (all 3 formats) | ≤10 minutes |
| NFR-005 | System availability | 99.5% uptime |

### 4.2 Security & Privacy

| ID | Requirement | Standard |
|---|---|---|
| NFR-006 | All API keys stored in vault (HashiCorp Vault / AWS Secrets Manager) | SOC 2 Type II |
| NFR-007 | Research data encrypted at rest (AES-256) and in transit (TLS 1.3) | ISO 27001 |
| NFR-008 | Subscriber PII handled per GDPR / PDPA (Singapore) | PDPA 2020 |
| NFR-009 | Audit logging of all agent actions | Immutable logs, 7-year retention |
| NFR-010 | Human-in-the-loop checkpoints at: hypothesis approval, critic loop escalation, pre-publish | Mandatory |

### 4.3 Cost Optimization

| ID | Requirement | Target |
|---|---|---|
| NFR-011 | Model tiering: 60% of calls use standard models, 30% premium, 10% extended thinking | Cost per research paper ≤$50 USD |
| NFR-012 | Token budget enforcement per agent | Hard limits with graceful degradation |
| NFR-013 | Caching of literature search results | 24-hour TTL; reduces API calls by ~40% |

### 4.4 Observability

| ID | Requirement | Tool |
|---|---|---|
| NFR-014 | Full trace logging per pipeline run | LangSmith / Langfuse / AgentOps |
| NFR-015 | Cost tracking per research project | Custom dashboard |
| NFR-016 | Agent performance metrics: accuracy, latency, token usage | Prometheus + Grafana |
| NFR-017 | Human checkpoint notification (email + SMS) | Twilio + SendGrid |

---

## 5. INTEGRATION ARCHITECTURE

### 5.1 Cloud Deployment

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLOUD INFRASTRUCTURE                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   CrewAI    │  │  Moonshot   │  │  Anthropic  │  │   MCP Server    │ │
│  │   Runtime   │  │  Kimi API   │  │  Claude API │  │    Registry     │ │
│  │  (AWS/GCP)  │  │  (Kimi-k3)  │  │ (Opus/Sonn) │  │  (Local/Cloud)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │                │                │                  │          │
│         └────────────────┴────────────────┴──────────────────┘          │
│                                    │                                    │
│                           ┌────────▼────────┐                          │
│                           │  Agent Network  │                          │
│                           │  (Docker/K8s)   │                          │
│                           └────────┬────────┘                          │
│                                    │                                    │
│         ┌──────────────────────────┼──────────────────────────┐         │
│         │                          │                          │         │
│    ┌────▼────┐              ┌──────▼──────┐            ┌──────▼──────┐  │
│    │PostgreSQL│              │   Redis     │            │  Object     │  │
│    │ (State)  │              │  (Cache)    │            │  Storage    │  │
│    └─────────┘              └─────────────┘            │  (S3/GCS)   │  │
│                                                        └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Technology Stack

| Layer | Technology |
|---|---|
| Orchestration | **CrewAI Multi-Agent Framework (Python)** |
| State/Memory | Redis + CrewAI Memory System |
| File Storage | AWS S3 / Google Cloud Storage |
| Document Processing | Pandoc (Markdown↔DOCX), LaTeX (PDF), WeasyPrint (fallback) |
| Visualization | Python matplotlib, seaborn, plotly |
| Image Generation | DALL-E 4 API, Midjourney API, Stable Diffusion 3.5 |
| Email | SendGrid API |
| Monitoring | AgentOps / LangSmith / Grafana |
| Secrets | HashiCorp Vault |

---

## 6. HUMAN-IN-THE-LOOP CHECKPOINTS

| Checkpoint | Trigger | Human Action | Timeout |
|---|---|---|---|
| CP-01 | Hypothesis formalized | Approve/reject/modify formalized hypothesis (`human_input=True`) | 72 hours |
| CP-02 | Critic loop ≥3 iterations | Manual review of research quality / force-pass | 48 hours |
| CP-03 | Pre-publish | Final approval of Substack article (`human_input=True`) | 24 hours |
| CP-04 | Emergency stop | Any agent can flag for human review | Immediate |

---

## 7. GLOSSARY

| Term | Definition |
|---|---|
| AuDHD | Combined Autism Spectrum Disorder (ASD) + Attention Deficit Hyperactivity Disorder (ADHD) presentation |
| MCP | Model Context Protocol — standardized tool interface for AI agents |
| HITL | Human-in-the-Loop — mandatory human approval gates |
| PRISMA | Preferred Reporting Items for Systematic Reviews and Meta-Analyses |
| IMRaD | Introduction, Methods, Results, and Discussion — standard paper structure |
| OA | Open Access — freely available scientific literature |
| TL;DR | Too Long; Didn't Read — executive summary for quick consumption |

---

**Document Owner:** Research Infrastructure Team  
**Review Cycle:** Quarterly  
**Next Review:** 2026-10-23
