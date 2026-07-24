# Plan - Research Multi-Agent System (CrewAI)

We will integrate **AGENT-13: Hallucination & Grounding Verifier** as a core, un-bypassable gatekeeper across the entire multi-agent research workspace in the `/home/coder/research_multi_agent_system` directory. 

This update follows state-of-the-art AI safety standards and factual grounding guardrails (NLI validation, citation existence auditing, quotation verification, and numerical consistency checks) to completely eliminate AI hallucinations (fabricated papers, DOIs, direct quotes, or statistics) across all generated files.

---

## 1. Directory Structure

No files are added to the directory structure; instead, we will update the existing core files:

```text
research_multi_agent_system/
├── PLAN.md                                    # Updated implementation plan
├── README.md                                  # Updated with AGENT-13 architecture
├── config/
│   ├── agents.yaml                            # Updated with hallucination_verifier agent config
│   └── tasks.yaml                             # Updated with three distinct verification tasks
├── src/
│   └── crew.py                                # Updated with AGENT-13 and verification task definitions
│
│   # 🧩 CORE SPECIFICATION DOCUMENTS:
├── SKILL.md_AuDHD_MultiAgent_System.md        # Updated with SKILL-13-001 Grounding Verification
├── Schema_AuDHD_MultiAgent_System.md         # Updated with verification states and schemas
├── AgentCards_AuDHD_MultiAgent_System.md     # Updated with AGENT-13 Card and 13x13 matrix
└── FRD_AuDHD_MultiAgent_Research_System.md   # Updated with AGENT-13 functional requirements
```

---

## 2. AGENT-13 Design Specifications

* **Agent ID:** `hallucination_verifier` (AGENT-13)
* **Name:** Hallucination & Grounding Verifier
* **Role:** Detect and eliminate fabricated citations, DOIs, statistical numbers, and direct quotes across all synthesized research and articles.
* **Model Tier:** Premium (Claude Opus 4.8 / Gemini 2.5 Pro / Claude Sonnet 4.6 with `temperature=0.0`).
* **Evaluation Guardrails:**
  1. **Citation Auditing:** Verify DOIs against Crossref/Semantic Scholar registries (or mock tools) to guarantee paper existence.
  2. **NLI Grounding Check:** Validate that claims made in the synthesis are mathematically and contextually supported by raw paper extraction sources.
  3. **Quotation Verification:** Check direct quotes against extracted PDF snippets to enforce exact matches.
  4. **Numerical Alignment:** Audit all sample sizes ($N$), p-values ($p$), and effect sizes to prevent rounding drift or fabrication.

---

## 3. Detailed Modification Steps

1. **Step 1: Configuration Updates (`config/`)**
   - **`config/agents.yaml`**: Add the `hallucination_verifier` role, goal, and strict, adversarial safety backstory.
   - **`config/tasks.yaml`**: Add three distinct validation tasks:
     * `verify_consolidated_report_task`: Runs immediately after `manager` outputs findings.
     * `verify_research_paper_task`: Runs immediately after `editor` formats the academic report.
     * `verify_substack_article_task`: Runs immediately after `writer` drafts the accessible Substack post.

2. **Step 2: Python Code Updates (`src/`)**
   - **`src/crew.py`**:
     * Add `hallucination_verifier` method decorated with `@agent`.
     * Add three verification tasks: `verify_consolidated_report_task`, `verify_research_paper_task`, and `verify_substack_article_task` decorated with `@task`.
     * Update `crew()` to register the new agent and map the three verification tasks sequentially in the active pipeline.

3. **Step 3: Specification Documents Updates**
   - **`SKILL.md`**: Add `SKILL-13-001: Grounding & Factual Verification` outlining execution protocols, quality scores, and failure recoveries.
   - **`Schema.md`**: Add verification state fields (`verification_reports`, `all_claims_grounded`) and state machine changes.
   - **`AgentCards.md`**: Append the complete AGENT-13 card, update resource allocation (average run rises to ~175K tokens / $32.00 USD), and update the interaction matrix to a 13x13 grid.
   - **`FRD.md`**: Insert Agent-13 detailed functional requirements (FR-A13-001 through FR-A13-008) and update the top-level architecture flowchart.
   - **`README.md`**: Revise the visual flowchart to highlight the verification gates before any asset proceeds to the critics or publishing.
