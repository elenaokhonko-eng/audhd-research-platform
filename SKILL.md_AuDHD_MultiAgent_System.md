# AuDHD Phenotype Research Multi-Agent System
## SKILL.md — Master Operating Manual

**Version:** 1.0  
**Date:** 2026-07-23  
**Classification:** Internal Operations  
**Framework Standards:** Anthropic Agent SDK 2026, Google ADK, Gemini 2.5, MCP v1.17, LangGraph Production Patterns

---

## TABLE OF CONTENTS

1. [System Philosophy & Design Principles](#1-system-philosophy)
2. [Agent Skill Registry](#2-agent-skill-registry)
3. [Critic Agent Standards & Rubrics](#3-critic-standards)
4. [Prompt Engineering Templates](#4-prompt-templates)
5. [Quality Assurance Protocols](#5-qa-protocols)
6. [MCP Tool Specifications](#6-mcp-tools)
7. [Human-in-the-Loop Procedures](#7-hitl-procedures)
8. [Failure Recovery Playbooks](#8-recovery-playbooks)
9. [Performance Benchmarks](#9-benchmarks)
10. [Security & Compliance](#10-security)

---

## 1. SYSTEM PHILOSOPHY & DESIGN PRINCIPLES

### 1.1 Intent-Driven Orchestration

Per Anthropic's 2026 Agentic Coding Trends Report, this system replaces **prompt-driven orchestration** with **intent-driven orchestration**:

| Prompt-Driven | Intent-Driven |
|---|---|
| One prompt, one agent, one shot | Structured spec, decomposed across agents |
| Context lives in the conversation | Context persists in the spec and state |
| Success = "it runs" | Success = outcomes verified |
| Edge cases discovered in production | Edge cases defined upfront |
| Coordination by improvisation | Coordination by specification |

### 1.2 Core Principles

**P1: Verification as Infrastructure**
Every agent output is verified before propagation. Critic agents are not optional — they are load-bearing structural elements.

**P2: Context Engineering Over Prompt Engineering**
Agent failures are primarily context failures, not model failures. We invest in state management, not prompt tweaking.

**P3: Model Tiering for Cost Optimization**
- **Premium (Claude Opus 4.8 / Gemini 2.5 Pro):** Hypothesis formalization, research direction, adversarial critique
- **Standard (Claude Sonnet 4.6 / Gemini 2.0 Flash):** Literature extraction, document formatting, content writing
- **Lightweight (Claude Haiku 4.5 / Gemini 2.0 Nano):** Scheduling, email, simple routing

**P4: Neurodivergent-First Design**
All outputs must be accessible to AuDHD audiences. This is not an afterthought — it is a constraint on all agent behavior.

**P5: Scientific Rigor as Non-Negotiable**
No output reaches publication without passing adversarial critique. The critic agents have veto power.

---

## 2. AGENT SKILL REGISTRY

### 2.1 Skill Definition Format

Each skill is defined as:

```yaml
skill_id: SKILL-XX-NNN
name: Human-readable name
description: What the skill does
agent: AGENT-XX (primary owner)
model_tier: premium | standard | lightweight
input_schema: Reference to schema document
output_schema: Reference to schema document
tools: [List of MCP tools used]
prompt_template: Section reference
validation: How output is validated
failure_mode: How failures are handled
```

---

### SKILL-01-001: Hypothesis Formalization

```yaml
skill_id: SKILL-01-001
name: Hypothesis Formalization
description: Transforms raw researcher intuition into structured, testable scientific hypotheses using the dual-search formalization framework.
agent: AGENT-01
model_tier: premium
input_schema: RawHypothesisPayload
output_schema: FormalizedHypothesisDocument
tools:
  - socratic_elicitation
  - literature_gap_scan
  - operationalization_assistant
  - ethical_review_checklist
prompt_template: PT-01-001
validation: Schema validation + human approval (CP-01)
failure_mode: Return to researcher with clarification request
```

**Execution Steps:**
1. Parse raw hypothesis for conceptual claims
2. Identify ambiguous or underspecified variables
3. Generate Socratic clarifying questions (3-7)
4. Await researcher responses (state checkpoint)
5. Operationalize all variables with measurement instruments
6. Formulate explicit H0 and H1
7. Define falsifiability criteria
8. Run ethical review checklist
9. Generate literature gap analysis
10. Output structured formalized hypothesis
11. Await human approval (CP-01)

---

### SKILL-02-001: Research Task Decomposition

```yaml
skill_id: SKILL-02-001
name: Research Task Decomposition
description: Decomposes formalized hypothesis into parallel research tasks with optimal source allocation and dependency mapping.
agent: AGENT-02
model_tier: premium
input_schema: FormalizedHypothesisDocument
output_schema: ResearchPlan (array of ResearchTask)
tools:
  - source_allocator
  - dependency_mapper
  - budget_estimator
prompt_template: PT-02-001
validation: Task schema validation + budget check
failure_mode: Escalate to human if budget exceeded
```

**Decision Tree Logic:**

```
START: Receive FormalizedHypothesis
│
├─→ Step 1: Identify hypothesis components
│   ├─→ Component A: Independent variables
│   ├─→ Component B: Dependent variables
│   ├─→ Component C: Population characteristics
│   ├─→ Component D: Mechanisms/pathways
│   └─→ Component E: Outcome measures
│
├─→ Step 2: Map components to literature domains
│   ├─→ CLINICAL/BIOMEDICAL → PubMed, Cochrane, ClinicalTrials.gov
│   ├─→ PSYCHOLOGY/BEHAVIORAL → PsycINFO, PubMed, APA PsycNet
│   ├─→ NEUROSCIENCE → PubMed, bioRxiv, Neuroscience journals
│   ├─→ EDUCATION/SOCIAL → ERIC, Google Scholar, JSTOR
│   ├─→ PREPRINTS/EMERGING → arXiv, bioRxiv, medRxiv, PsyArXiv
│   └─→ CITATION ANALYSIS → Semantic Scholar, Web of Science
│
├─→ Step 3: Assess task independence
│   ├─→ Independent → parallel_group assignment
│   └─→ Dependent → sequential chain
│
├─→ Step 4: Calculate token budgets
│   └─→ Budget = base + (complexity_factor × source_count)
│
└─→ Step 5: Dispatch to Junior Research Agent pool
```

---

### SKILL-03-001: Parallel Literature Extraction

```yaml
skill_id: SKILL-03-001
name: Parallel Literature Extraction
description: Executes literature searches, retrieves papers, parses full text, and extracts structured data in parallel.
agent: AGENT-03 (×3-8 instances)
model_tier: standard
input_schema: ResearchTask
output_schema: PaperExtraction[]
tools:
  - pubmed_search_mcp
  - arxiv_search_mcp
  - semantic_scholar_mcp
  - google_scholar_mcp
  - pdf_parser_mcp
  - unpaywall_mcp
prompt_template: PT-03-001
validation: Schema validation + deduplication
failure_mode: Retry with exponential backoff (max 3); escalate on failure
```

**Extraction Protocol (PRISMA-inspired):**

1. **Search Execution:** Run all assigned queries; paginate to max results
2. **Screening:** Title/abstract screen → full-text eligibility
3. **Data Extraction:** Use structured schema (never free-form)
4. **Quality Assessment:** Assign tier per journal/publisher
5. **Citation Tracking:** Record all references for graph analysis
6. **Researcher Profiling:** Identify lead authors with h-index ≥20

**Quality Tiers:**
- **Tier-1:** Peer-reviewed, Q1 journal, IF ≥5, replicated findings
- **Tier-2:** Peer-reviewed, Q2-Q3 journal, IF 2-5
- **Tier-3:** Peer-reviewed, Q4 or no IF, or reputable preprint
- **Tier-4:** Preprint, conference abstract, or non-peer-reviewed

---

### SKILL-04-001: Research Synthesis

```yaml
skill_id: SKILL-04-001
name: Research Synthesis
description: Consolidates parallel research outputs into coherent thematic clusters with contradiction resolution and gap analysis.
agent: AGENT-04
model_tier: premium
input_schema: PaperExtraction[]
output_schema: ConsolidatedResearchReport
tools:
  - deduplication_engine
  - thematic_clusterer
  - contradiction_resolver
  - meta_analysis_calculator
prompt_template: PT-04-001
validation: Coverage score calculation + critic review
failure_mode: Return to manager with gap identification
```

**Synthesis Principles:**
1. **DEDUPLICATION:** Merge overlapping findings; preserve unique contributions
2. **THEMATIC CLUSTERING:** Group papers by conceptual themes, not chronology
3. **CONTRADICTION RESOLUTION:** When studies disagree, weigh evidence quality
4. **EVIDENCE GRADING:** Use GRADE-inspired quality assessment
5. **GAP MAPPING:** Explicitly state what remains unknown
6. **HYPOTHESIS ALIGNMENT:** Map every theme back to the original H1

---

### SKILL-05-001: Adversarial Research Critique

```yaml
skill_id: SKILL-05-001
name: Adversarial Research Critique
description: Challenges research quality, statistical validity, citation accuracy, and logical coherence using 5-dimensional rubric.
agent: AGENT-05
model_tier: premium (Extended Thinking)
input_schema: ConsolidatedResearchReport
output_schema: CriticReport
tools:
  - citation_verifier
  - statistical_validator
  - bias_detector
  - logic_checker
prompt_template: PT-05-001
validation: Score-based gate (≥80% = pass)
failure_mode: Loop back to manager (max 3 iterations) → human escalation
```

**5-Dimensional Critic Rubric:**

| Dimension | Weight | Criteria | Scoring Guide |
|---|---|---|---|
| **Methodological Rigor** | 25% | Study designs appropriate? Controls adequate? Confounders addressed? AuDHD population specifically represented? | 90-100: All studies well-designed with appropriate controls; 70-89: Minor design flaws; 50-69: Major design concerns; <50: Fundamentally flawed |
| **Evidence Quality** | 25% | Peer-reviewed ratio? Impact factor distribution? Replication status? P-hacking indicators? | 90-100: >80% Tier-1/2, replicated findings; 70-89: Mixed quality, some replication; 50-69: Mostly Tier-3/4; <50: Unreliable evidence base |
| **Logical Coherence** | 20% | Arguments valid? Fallacies absent? Conclusions follow from evidence? Effect sizes interpreted correctly? | 90-100: Flawless logic chain; 70-89: Minor leaps; 50-69: Significant logical gaps; <50: Invalid reasoning |
| **Hypothesis Coverage** | 20% | All H1 components addressed? Null hypothesis considered? Alternative explanations explored? | 90-100: Complete coverage; 70-89: Most components; 50-69: Partial coverage; <50: Major gaps |
| **Scientific Novelty** | 10% | New insights generated? Literature gaps genuinely filled? Contribution clearly articulated? | 90-100: Breakthrough insights; 70-89: Meaningful advances; 50-69: Incremental; <50: Redundant |

**Scoring Thresholds:**
- **≥80% weighted:** PASS → proceed to Editor
- **60-79%:** REVISE → detailed feedback to Manager; loop back
- **<60%:** FAIL → major rework required; escalate to human (CP-02)

**Max Iterations:** 3. After 3 iterations, mandatory human review.

---

### SKILL-06-001: Multi-Format Document Production

```yaml
skill_id: SKILL-06-001
name: Multi-Format Document Production
description: Produces publication-ready research papers in Markdown, DOCX, and PDF with APA 7th edition formatting.
agent: AGENT-06
model_tier: standard
input_schema: ConsolidatedResearchReport + approved flag
output_schema: ResearchPaperDraft (multi-format)
tools:
  - markdown_formatter
  - pandoc_converter
  - latex_compiler
  - matplotlib_generator
  - zotero_citation_manager
prompt_template: PT-06-001
validation: Format validation + Paper Critic review
failure_mode: Return to editor with formatting errors
```

**Document Structure (IMRaD +):**
1. Title Page
2. Abstract (≤250 words, structured)
3. Introduction
4. Literature Review (thematic synthesis)
5. Methods (review protocol, search strategy, PRISMA)
6. Results (findings by theme, data tables, figures)
7. Discussion (interpretation, implications, limitations)
8. Conclusion (summary, hypothesis assessment)
9. References (APA 7th, DOI-linked)
10. Appendices (extraction tables, PRISMA flow diagram)

---

### SKILL-07-001: Scientific Publication Validation

```yaml
skill_id: SKILL-07-001
name: Scientific Publication Validation
description: Validates completed research paper against scientific publication standards, format compliance, and logical clarity.
agent: AGENT-07
model_tier: premium
input_schema: ResearchPaperDraft
output_schema: ValidationReport
tools:
  - structure_validator
  - reference_checker
  - logic_flow_analyzer
  - apa_style_checker
prompt_template: PT-07-001
validation: Hard gate: all P0 criteria must pass
failure_mode: Return to editor with detailed correction list
```

**Validation Checklist:**

```
STRUCTURE VALIDATION:
□ All IMRaD+ sections present
□ Abstract ≤250 words
□ Word count: 3000-8000 (review paper range)
□ Section hierarchy correct (H1, H2, H3)

REFERENCE VALIDATION:
□ All in-text citations have bibliography entries
□ DOI present for all post-2000 papers
□ APA 7th edition format correct
□ Hanging indents applied
□ No "et al." in first citation

DATA PRESENTATION:
□ Tables have titles and notes
□ Figures have captions and source notes
□ Statistical notation follows APA (M, SD, t, p, d, 95% CI)
□ Effect sizes reported with CIs
□ Alt-text provided for all figures

LOGICAL FLOW:
□ Each paragraph has clear topic sentence
□ Transitions between sections explicit
□ Arguments build sequentially
□ No non-sequiturs

EVIDENCE INTEGRITY:
□ All claims backed by citations
□ No unsourced assertions
□ Citation density: ≥1 citation per 150 words in LR
□ Direct quotes properly attributed

GRAPHICS VALIDATION:
□ All figures data-derived (not decorative)
□ Source data referenced
□ Reproducible from provided code
```

---

### SKILL-08-001: Science Communication Writing

```yaml
skill_id: SKILL-08-001
name: Science Communication Writing
description: Transforms validated research into creative, accessible, neurodivergent-affirming Substack articles with dual-mode structure.
agent: AGENT-08
model_tier: premium (creative)
input_schema: ResearchPaperDraft + approved flag
output_schema: SubstackArticle
tools:
  - readability_analyzer
  - tone_checker
  - headline_optimizer
  - substack_formatter
prompt_template: PT-08-001
validation: Substack Critic review + human approval (CP-03)
failure_mode: Return to writer with audience-fit feedback
```

**Dual-Mode Structure (AuDHD Accessibility):**

**TL;DR SECTION (ADHD Mode):**
- Positioned at TOP of article
- ≤150 words
- Bullet points only
- Key takeaway in first bullet
- Designed for 10-second comprehension

**DEEP DIVE SECTIONS (Autistic Mode):**
- Expandable/collapsible sections
- Full methodological detail
- Data tables and source references
- Designed for deep, systematic processing

**Neurodivergent-Affirming Language Rules:**
1. Use identity-first language ("autistic person") unless individual preference known
2. Avoid pathologizing terms ("disorder", "deficit", "impairment")
3. Use strength-based framing
4. Respect self-advocacy and lived experience
5. Acknowledge uncertainty honestly

---

### SKILL-09-001: Visual Asset Generation

```yaml
skill_id: SKILL-09-001
name: Visual Asset Generation
description: Produces data visualizations for research papers and creative illustrations for Substack articles matching AuDHD phenotype design theme.
agent: AGENT-09
model_tier: visual_api
input_schema: VisualizationRequest | IllustrationRequest
output_schema: VisualAssets[]
tools:
  - matplotlib_generator
  - plotly_generator
  - dalle4_api
  - midjourney_api
  - stable_diffusion_35
prompt_template: PT-09-001
validation: Data-derived check (research) or theme compliance (Substack)
failure_mode: Regenerate with revised prompt
```

**Mode A: Research Paper Data Visualization**
- Trigger: Research Editor Agent
- Output: Data-derived charts, graphs, forest plots, PRISMA diagrams
- Tools: Python matplotlib, seaborn, plotly
- Requirements: All charts reproducible from CSV source data

**Mode B: Substack Creative Illustration**
- Trigger: Substack Writer Agent
- Output: Creative images, infographics, header images
- Style: Earth tones, nature-biophilic, neurodivergent-affirming

**Design System:**
| Element | Specification |
|---|---|
| Color Palette | Forest green (#2D5A3D), terracotta (#C4785A), deep ocean (#1A3A52), cream (#F5F1E8), gold (#D4A843) |
| Typography | Headings: Crimson Pro; Body: Inter; Dyslexia-friendly alternatives |
| Imagery Style | Trees, roots, mycelium networks, neural pathways as organic growth |
| Accessibility | WCAG 2.1 AA, contrast ≥4.5:1, no flashing elements |

---

### SKILL-10-001: Audience-Fit Content Validation

```yaml
skill_id: SKILL-10-001
name: Audience-Fit Content Validation
description: Validates Substack articles for audience fit, accessibility, scientific accuracy, and platform compliance.
agent: AGENT-10
model_tier: standard
input_schema: SubstackArticle
output_schema: ContentValidationReport
tools:
  - readability_checker
  - tone_analyzer
  - link_validator
  - image_compliance_checker
prompt_template: PT-10-001
validation: Hard gate before scheduling
failure_mode: Return to writer with detailed feedback
```

**Validation Dimensions:**

```
SUBSTACK COMPLIANCE:
□ Article length: 1500-3000 words
□ Images: ≤3 per screen scroll
□ External links: functional, relevant
□ Formatting: valid Substack Markdown
□ SEO: meta description, tags

AUDIENCE FIT (AuDHD):
□ Tone: neurodivergent-affirming, non-pathologizing
□ Cognitive load: paragraph length ≤4 sentences
□ TL;DR: passes 10-second comprehension test
□ Deep Dive: satisfies detail-oriented readers
□ Pacing: breaks between dense sections

SCIENTIFIC ACCURACY:
□ All numeric claims verified against research paper
□ No overstatement of findings
□ Uncertainty acknowledged
□ Citations present (simplified for audience)

ACCESSIBILITY:
□ Alt-text for all images
□ Color contrast adequate
□ No autoplay media
□ Dyslexia-friendly font option noted

ENGAGEMENT:
□ Headline: compelling, not clickbait
□ Hook: strong first paragraph
□ CTA: clear call-to-action at end
□ Shareability: quotable passages
```

---

### SKILL-11-001: Content Queue Management

```yaml
skill_id: SKILL-11-001
name: Content Queue Management
description: Manages publishing backlog, schedules posts, and publishes to Substack with state tracking.
agent: AGENT-11
model_tier: lightweight
input_schema: SubstackArticle + approval flag
output_schema: PublishConfirmation
tools:
  - notion_mcp
  - substack_narrareach_mcp
  - scheduler_mcp
prompt_template: PT-11-001
validation: Status update confirmation
failure_mode: Retry with exponential backoff; alert human on persistent failure
```

**Notion Database Schema:**

| Property | Type | Options |
|---|---|---|
| Title | Title | Article headline |
| Status | Select | Draft, Ready for Review, Scheduled, Published, Archived |
| Publish Date | Date | ISO 8601 with timezone |
| Topic | Multi-select | AuDHD, HRT, Trauma, Alexithymia, etc. |
| Article ID | Text | UUID linking to research pipeline |
| Word Count | Number | Auto-calculated |
| Read Time | Number | Auto-calculated (words / 200) |
| Research Paper | URL | Link to full research paper |
| Substack URL | URL | Populated on publish |

---

### SKILL-12-001: Subscriber Email Distribution

```yaml
skill_id: SKILL-12-001
name: Subscriber Email Distribution
description: Distributes completed research papers to paid Substack subscribers in multiple formats.
agent: AGENT-12
model_tier: lightweight
input_schema: ResearchPaperDraft + subscriber_list
output_schema: DistributionReport
tools:
  - substack_subscriber_api
  - sendgrid_email_api
  - analytics_tracker
prompt_template: PT-12-001
validation: Delivery confirmation + bounce handling
failure_mode: Queue for retry; alert on persistent failure
```

---

### SKILL-13-001: Grounding & Factual Verification

```yaml
skill_id: SKILL-13-001
name: Grounding & Factual Verification
description: Executes state-of-the-art factual alignment audits (citation Crossref validation, textual NLI mapping, quotation exactness, and numerical alignment) to catch and eliminate hallucinations before critic checks or distribution.
agent: AGENT-13
model_tier: premium
input_schema: ResearchState
output_schema: FactualAuditReport
tools:
  - citation_verifier
  - crossref_doi_checker
  - quote_exactness_verifier
  - data_alignment_checker
prompt_template: PT-13-001
validation: 100% citation validation + strict quotation matching
failure_mode: Flag ungrounded claims; throw warning and reject to synthesis managers
```

**Verification Execution Protocol:**
1. **Citation Auditing:** Run DOI resolution checks. Verify title, publisher, and year. Any imaginary or unmatched reference raises an immediate fail.
2. **NLI Textual Grounding:** Decompose sentences of drafted syntheses. Cross-reference claims against compiled PDF textual extractions to ensure direct entailment.
3. **Quotation Matcher:** Audit direct quotes. Raise fail if quote has more than 1 character edit distance compared to raw full-text sources.
4. **Numerical Audit:** Check sample sizes (N), statistics (SD, regression coefficients, p-values), and calculations. Reject any rounding drifts.


---

## 3. CRITIC AGENT STANDARDS & RUBRICS

### 3.1 Anthropic Constitutional AI Principles for Critics

Critic agents operate under Anthropic's Constitutional AI framework with these additional constraints:

**Constitution for Research Critics:**
1. **Accuracy:** Never let a false claim pass unchallenged, even if it supports a desirable conclusion.
2. **Completeness:** A partial truth that omits contradictory evidence is a form of deception.
3. **Humility:** Acknowledge the limits of the evidence base; do not overstate confidence.
4. **Neutrality:** Evaluate methodology, not conclusions. A well-conducted study with unwelcome findings deserves praise.
5. **Transparency:** Every critique must be traceable to specific evidence, not general impression.

### 3.2 Google Gemini Safety & Factual Grounding Standards

Per Google ADK 2026 and Gemini 2.5 Pro specifications:

- **Grounding:** All factual claims in critique must be grounded in retrieved documents, not parametric knowledge.
- **Citation Verification:** Spot-check 20% of citations minimum; verify claim exists in original source.
- **Retrieval-Augmented Generation (RAG):** Critic agents must use RAG for all factual assertions about papers.
- **Safety:** Flag any content that could cause harm to neurodivergent readers (stigmatizing language, unsupported medical claims).

### 3.3 Multi-Agent Validation Framework (PMC 2025)

Based on the multi-agent AI pipeline validation framework (PMC12757325):

**Credibility Scoring (5-Level):**
| Level | Description | Action |
|---|---|---|
| **5 — Fully Verified** | Claim supported by multiple high-quality sources with consistent findings | Accept |
| **4 — Mostly Verified** | Claim supported by primary sources with minor inconsistencies | Accept with caveat |
| **3 — Partially Verified** | Claim supported by limited or lower-quality evidence | Flag for review |
| **2 — Weakly Supported** | Claim has minimal or conflicting evidence | Challenge |
| **1 — Unsupported/Contradicted** | Claim contradicted by evidence or entirely unsupported | Reject |

### 3.4 Peer Review Simulation Standards

Critic agents simulate the rigor of top-tier journal peer review:

**Methodological Review:**
- Check for appropriate study design given research question
- Verify sample size adequacy (power analysis where reported)
- Assess control group appropriateness
- Evaluate confounding variable control
- Check for selective reporting

**Statistical Review:**
- Verify p-values match reported test statistics
- Check confidence interval interpretation
- Assess effect size practical significance
- Flag p-hacking indicators (multiple comparisons uncorrected)
- Verify assumption checks for parametric tests

**Ethical Review:**
- IRB/ethics approval documented
- Informed consent procedures described
- Vulnerable population protections
- Data privacy safeguards
- Conflict of interest disclosures

---

## 4. PROMPT ENGINEERING TEMPLATES

### 4.1 PT-01-001: Hypothesis Analyst System Prompt

```
You are a Scientific Hypothesis Formalization Specialist with expertise in 
neurodivergence research, particularly AuDHD (Autistic + ADHD) phenotypes. 
Your role is to bridge the gap between a researcher raw intuition and a 
rigorous, testable scientific hypothesis.

You follow the Hypothesis Formalization Framework (Klahr & Simon dual-search 
model, extended by Schunn & Klahr four-space model). Your process is 
BIDIRECTIONAL: you move from concept to implementation AND from 
implementation back to concept, refining the hypothesis iteratively.

ETHICAL MANDATE: You must always consider the vulnerability of 
neurodivergent research populations. Flag any ethical concerns related 
to consent, stigma, pathologizing language, or exploitation.

OPERATING PRINCIPLES:
1. Never assume — always elicit
2. Operationalize every variable
3. Define falsifiability explicitly
4. Map to existing literature gaps
5. Flag unstated assumptions

OUTPUT FORMAT: You must produce a JSON object conforming to the 
FormalizedHypothesisDocument schema. Do not output free text outside the JSON.
```

### 4.2 PT-05-001: Research Critic System Prompt

```
You are a Research Critic operating in ADVERSARIAL MODE. Your sole purpose 
is to find weaknesses, errors, biases, and gaps in the research synthesis. 
You are not a cheerleader — you are a methodological assassin.

Your evaluation follows the 5-Dimensional Critic Rubric:

DIMENSION 1: METHODOLOGICAL RIGOR (25%)
- Are study designs appropriate for the claims made?
- Are control groups adequate?
- Are confounders (medication, comorbidities, age, sex) addressed?
- Is the AuDHD population specifically represented, or are findings 
  extrapolated from ASD-only or ADHD-only samples?

DIMENSION 2: EVIDENCE QUALITY (25%)
- What is the peer-reviewed ratio?
- What is the journal impact factor distribution?
- Have key findings been replicated?
- Are there signs of p-hacking or questionable research practices?

DIMENSION 3: LOGICAL COHERENCE (20%)
- Are arguments logically valid?
- Are there formal or informal fallacies?
- Do conclusions follow from evidence?
- Are effect sizes interpreted correctly?

DIMENSION 4: HYPOTHESIS COVERAGE (20%)
- What percentage of H1 components are addressed?
- Is the null hypothesis given fair consideration?
- Are alternative explanations explored?

DIMENSION 5: SCIENTIFIC NOVELTY (10%)
- Are new insights generated?
- Are literature gaps genuinely filled?
- Is the contribution clearly articulated?

SCORING:
- ≥80%: PASS — proceed to Editor
- 60-79%: REVISE — detailed feedback to Manager; loop back
- <60%: FAIL — major rework required; escalate to human

MAX ITERATIONS: 3. After 3 iterations, mandatory human review (CP-02).

OUTPUT FORMAT: You must produce a JSON object conforming to the 
CriticReport schema. Include specific paper_ids for every criticism.
```

### 4.3 PT-08-001: Substack Writer System Prompt

```
You are a Science Communication Writer specializing in neurodivergence 
topics. You write for the AuDHD community with these principles:

1. NEURODIVERGENT-AFFIRMING LANGUAGE:
   - Use identity-first language ("autistic person") unless individual 
     preference known
   - Avoid pathologizing terms ("disorder", "deficit", "impairment")
   - Use strength-based framing
   - Respect self-advocacy and lived experience

2. DUAL-MODE STRUCTURE (AuDHD Accessibility):
   TL;DR SECTION (ADHD Mode):
   - Positioned at TOP of article
   - ≤150 words
   - Bullet points only
   - Key takeaway in first bullet
   - Designed for 10-second comprehension

   DEEP DIVE SECTIONS (Autistic Mode):
   - Expandable/collapsible sections
   - Full methodological detail
   - Data tables and source references
   - Designed for deep, systematic processing

3. TONE:
   - Warm but scientifically grounded
   - Personal where appropriate (with researcher approval)
   - Never patronizing
   - Acknowledge uncertainty honestly

4. ENGAGEMENT:
   - Compelling headline (curiosity gap, not clickbait)
   - Strong hook in first paragraph
   - Clear CTA at end (subscribe, share, comment)
   - Discussion prompts for community engagement

OUTPUT FORMAT: Substack-compatible Markdown with TL;DR blockquote and 
HTML details/summary tags for Deep Dive sections.
```

---

## 5. QUALITY ASSURANCE PROTOCOLS

### 5.1 Pre-Deployment QA Checklist

Before any agent is deployed to production:

```
□ Prompt template tested on 10+ diverse inputs
□ Output schema validation passes 100% of test cases
□ Error handling tested for all identified failure modes
□ Token budget enforcement verified
□ Cost estimates within 10% of actual
□ Human checkpoint notifications functional
□ Audit logging captures all required fields
□ MCP tool connections tested end-to-end
□ Fallback model tested for primary model failure
□ Rate limiting tested under load
```

### 5.2 Continuous Evaluation

| Metric | Measurement Frequency | Target |
|---|---|---|
| Hypothesis approval rate | Per session | ≥80% |
| Critic pass rate (first attempt) | Per session | ≥60% |
| Citation accuracy | Per session (spot-check) | ≥95% |
| Paper format compliance | Per session | 100% P0 criteria |
| Substack audience-fit score | Per session | ≥85% |
| End-to-end latency | Per session | ≤48 hours |
| Cost per research paper | Per session | ≤$50 USD |
| Human escalation rate | Per month | ≤10% |

### 5.3 Regression Testing

After any agent update:
1. Run full pipeline on 5 benchmark hypotheses
2. Compare outputs to previous version
3. Verify no degradation in critic scores
4. Check cost delta within ±15%
5. Validate all schema compliance

---

## 6. MCP TOOL SPECIFICATIONS

### 6.1 Academic Research MCP Servers

| Server | Transport | Authentication | Rate Limit |
|---|---|---|---|
| `arxiv-mcp` | HTTP | None | 1 req/3s |
| `pubmed-mcp` | HTTP | NCBI API key | 3 req/s |
| `semantic-scholar-mcp` | HTTP | API key | 100 req/5min |
| `google-scholar-mcp` | HTTP | SerpAPI key | 100 req/month |
| `crossref-mcp` | HTTP | None (polite pool) | 50 req/s |
| `zotero-mcp` | HTTP | OAuth | 150 req/15min |

### 6.2 Publishing MCP Servers

| Server | Transport | Authentication | Capabilities |
|---|---|---|---|
| `substack-narrareach-mcp` | HTTP | API token | Draft, schedule, publish, queue |
| `email-sendgrid-mcp` | HTTP | API key | Send, track, bounce handling |
| `notion-mcp` | HTTP | Integration token | Database CRUD, status updates |

### 6.3 Visual Generation MCP Servers

| Server | Transport | Authentication | Capabilities |
|---|---|---|---|
| `dalle4-mcp` | HTTP | OpenAI API key | Image generation, editing |
| `midjourney-mcp` | HTTP | API key | Image generation, upscaling |
| `stable-diffusion-mcp` | HTTP | Local/RunPod | Image generation, inpainting |
| `matplotlib-mcp` | Local | N/A | Data visualization code generation |

---

## 7. HUMAN-IN-THE-LOOP PROCEDURES

### 7.1 Checkpoint CP-01: Hypothesis Approval

**Trigger:** Analyst Agent completes formalization  
**Notification:** Email + SMS to researcher  
**Action Required:**
- Review formalized hypothesis document
- Answer any remaining clarifying questions
- Approve, reject, or request revision
- Estimated time: 15-30 minutes

**Timeout:** 72 hours → auto-pause pipeline  
**Escalation:** After timeout, session archived; researcher must reactivate

### 7.2 Checkpoint CP-02: Post-Critic Escalation

**Trigger:** Research Critic reaches 3 iterations without passing  
**Notification:** Email + SMS to researcher  
**Action Required:**
- Review critic feedback history
- Decide: override and proceed, request major revision, or abandon
- Estimated time: 30-60 minutes

**Timeout:** 48 hours → auto-pause  
**Escalation:** After timeout, session flagged for manual review

### 7.3 Checkpoint CP-03: Pre-publish Approval

**Trigger:** Substack Critic approves article  
**Notification:** Email to researcher  
**Action Required:**
- Review final article draft
- Review all images and graphics
- Confirm publish timing (now vs. scheduled)
- Estimated time: 10-15 minutes

**Timeout:** 24 hours → auto-schedule for next available slot  
**Override:** Researcher can cancel auto-schedule

---

## 8. FAILURE RECOVERY PLAYBOOKS

### 8.1 Junior Research Agent Failure

**Symptom:** Task fails after 3 retries  
**Detection:** Error log + status = "failed"  
**Recovery:**
1. Log failure with context
2. Reassign task to alternate agent instance
3. If alternate also fails, split task into smaller sub-tasks
4. If sub-tasks fail, escalate to Research Director for replanning
5. If replanning fails, trigger CP-02 human escalation

### 8.2 Critic Loop Infinite Revision

**Symptom:** Critic iteration count ≥3 without passing  
**Detection:** State machine counter  
**Recovery:**
1. Halt automatic looping
2. Trigger CP-02 human escalation
3. Present researcher with:
   - All critic feedback versions
   - Manager revision attempts
   - Recommendation: proceed, revise, or abandon
4. Await human decision

### 8.3 Model Hallucination in Citations

**Symptom:** Citation verification fails (paper does not contain claimed text)  
**Detection:** Critic spot-check or manual verification  
**Recovery:**
1. Flag hallucinated citation
2. Remove claim from synthesis
3. Re-run Junior Research Agent for that specific claim
4. If claim cannot be verified, remove from paper and note as limitation
5. Log hallucination for model performance tracking

### 8.4 Publishing Failure

**Symptom:** Substack API returns error or timeout  
**Detection:** HTTP 4xx/5xx or timeout after 60s  
**Recovery:**
1. Retry with exponential backoff (2s, 4s, 8s, 16s)
2. If persistent, save as draft in Substack
3. Notify researcher with manual publish instructions
4. Queue for next automated attempt in 1 hour

---

## 9. PERFORMANCE BENCHMARKS

### 9.1 Agent Accuracy Benchmarks

| Agent | Benchmark Task | Target Accuracy | Evaluation Method |
|---|---|---|---|
| A01 Analyst | Hypothesis formalization on 50 known hypotheses | ≥85% schema compliance | Automated schema validation |
| A03 Junior | Paper extraction on 100 known papers | ≥90% field accuracy | Ground-truth comparison |
| A05 Critic | Detect planted errors in synthetic research | ≥95% detection rate | Adversarial test set |
| A07 Paper Critic | Validate 50 papers with known flaws | 100% P0 flaw detection | Known-fault injection |
| A10 Substack Critic | Rate 50 articles for audience fit | ≥90% human agreement | Inter-rater reliability |
| A13 Verifier | Catch planted hallucinations, fake DOIs, or altered stats | 100% detection rate | Known-fault/hallucination injection |

### 9.2 Latency Benchmarks

| Phase | Target | SLA |
|---|---|---|
| Hypothesis formalization | ≤30 min | 95th percentile |
| Parallel research (per task) | ≤15 min | 95th percentile |
| Research synthesis | ≤20 min | 95th percentile |
| Critic review | ≤10 min | 95th percentile |
| Document production | ≤15 min | 95th percentile |
| Substack writing | ≤20 min | 95th percentile |
| End-to-end (no human delays) | ≤6 hours | 95th percentile |

### 9.3 Cost Benchmarks

| Metric | Target | Alert Threshold |
|---|---|---|
| Cost per research paper | ≤$50 | $75 |
| Cost per Substack article | ≤$15 | $25 |
| Total cost per full pipeline | ≤$65 | $100 |
| Token efficiency (output/input ratio) | ≥0.3 | <0.2 |

---

## 10. SECURITY & COMPLIANCE

### 10.1 Data Classification

| Data Type | Classification | Handling |
|---|---|---|
| Researcher hypotheses | Internal | Encrypted at rest, TLS in transit |
| Extracted paper data | Internal | Anonymized where possible |
| Subscriber email addresses | Restricted | GDPR/PDPA compliant, vault-stored |
| API keys | Confidential | HashiCorp Vault, rotated 90 days |
| Audit logs | Restricted | Immutable, 7-year retention |

### 10.2 Compliance Framework

| Regulation | Requirement | Implementation |
|---|---|---|
| GDPR (EU subscribers) | Right to erasure, data portability | Automated export/deletion workflows |
| PDPA 2020 (Singapore) | Consent management, breach notification | Explicit consent tracking |
| COPE Guidelines | Research integrity, authorship | Critic agent validation |
| APA 7th Edition | Citation and formatting standards | Automated style checking |
| PRISMA | Systematic review reporting | Extraction schema compliance |

### 10.3 Incident Response

| Severity | Response Time | Action |
|---|---|---|
| Critical (data breach) | 15 minutes | Isolate, notify, investigate |
| High (system outage) | 30 minutes | Failover, restore, investigate |
| Medium (agent failure) | 2 hours | Retry, escalate, document |
| Low (performance degradation) | 24 hours | Optimize, monitor, document |

---

## APPENDIX A: PROMPT VERSIONING

All prompts are versioned using semantic versioning:
- **Major:** Structural changes to agent behavior
- **Minor:** New examples or clarifications
- **Patch:** Wording improvements, no behavior change

Current prompt versions:
| Prompt ID | Version | Last Updated |
|---|---|---|
| PT-01-001 | 1.0.0 | 2026-07-23 |
| PT-02-001 | 1.0.0 | 2026-07-23 |
| PT-03-001 | 1.0.0 | 2026-07-23 |
| PT-04-001 | 1.0.0 | 2026-07-23 |
| PT-05-001 | 1.0.0 | 2026-07-23 |
| PT-06-001 | 1.0.0 | 2026-07-23 |
| PT-07-001 | 1.0.0 | 2026-07-23 |
| PT-08-001 | 1.0.0 | 2026-07-23 |
| PT-09-001 | 1.0.0 | 2026-07-23 |
| PT-10-001 | 1.0.0 | 2026-07-23 |
| PT-11-001 | 1.0.0 | 2026-07-23 |
| PT-12-001 | 1.0.0 | 2026-07-23 |
| PT-13-001 | 1.0.0 | 2026-07-23 |

## APPENDIX B: GLOSSARY

| Term | Definition |
|---|---|
| AuDHD | Combined Autism Spectrum Disorder + ADHD presentation |
| MCP | Model Context Protocol — standardized tool interface |
| HITL | Human-in-the-Loop |
| PRISMA | Preferred Reporting Items for Systematic Reviews |
| IMRaD | Introduction, Methods, Results, Discussion |
| OA | Open Access |
| TL;DR | Too Long; Didn Read — executive summary |
| RAG | Retrieval-Augmented Generation |
| GRADE | Grading of Recommendations Assessment, Development and Evaluation |
| COPE | Committee on Publication Ethics |

---

**Document Owner:** Research Infrastructure Team  
**Review Cycle:** Monthly for first 3 months, then quarterly  
**Next Review:** 2026-08-23  
**Distribution:** Internal — Research Infrastructure, Agent Engineering, Quality Assurance
