# 10 · Borrow map: what to reuse, from where, into where

**Status:** Proposed for review · 2026-11-16 · Written for the coding agent that implements each stage
**Based on:** the review of 161 forked repositories (15 November 2026) and seven research briefs (16 November 2026). The full review tables are in the project notes; this page is the working subset.

## How to use this page

1. **Before writing a component, look it up here.** If a row exists, start from the named source instead of from a blank file.
2. **Each row says how to reuse:**

   | How | Meaning |
   | --- | --- |
   | **Dependency** | Install the published package or image, pinned. Do not copy its code. |
   | **Port** | Translate or copy the named files into the target path, adapt them, bring their tests. |
   | **Pattern** | Read the named files for the design; write our own code. Copy nothing. |
   | **Skill** | Prompt or skill text an agent loads; keep the file, credit the source. |
   | **Tool** | Run it in CI or as a developer tool; it is not part of the product. |

3. **Record every Port and Skill** in `THIRD_PARTY.md` at the repository root in the same pull request: source repository, commit, source path, licence, target path, what changed. Keep the source's licence header in the file. This is a build rule ([ADR 0012](../adr/0012-borrowed-code-provenance.md)).
4. **Licences.** Port code only from sources whose licence permits it (MIT, Apache-2.0, BSD and similar), keeping the notice. From unlicensed, non-commercial or copyleft sources take the idea only: this repository is public, so copying is distribution. The licence column says which is which. Inside the three **extractable packages** (`packages/substack-desk`, `packages/research-loop`, `packages/consent-deid`), if a file's origin needs a second look before release, give it a first-line comment `# PROVENANCE: <repo> <licence>: review before release`.
5. **Sources live in the owner's forks** at `github.com/elenaokhonko-eng/<repo>` unless a full name is given. Pin the commit you read.
6. **Never port a credential, a real endpoint response containing personal data, or an API key found in a source repository.**

## Target layout (v4)

```
apps/web/                         Next.js site, workspace, admin
services/platform-api/            M2, M12, M14 and admin, one service (Stage 1)
services/model-gateway/           gateway image pin and configuration (Stage 2)
services/tools-py/                Python tools that agents call: literature, scouts (Stage 2)
services/research-api/            Zones 2 and 3 (Stage 3)
packages/substack-desk/           extractable
packages/research-loop/           extractable (Stage 5)
packages/consent-deid/            extractable core of M5 (Stage 3)
packages/study-governance/        extractable: study pack schemas, rules, ethics templates, blocks, blueprints (Stage 3; templates earlier)
packages/events/                  event schemas shared by Python and TypeScript
agents/<team>/  agents/shared/    Genkit flows; gateway client, approvals, voice, writing checks
instruments/  studies/            registry, templates, protocols
config/platform/                  tiers.yaml, evidence_weights.yaml, gateway routing
infra/terraform/{modules,envs}    ops/scripts/    docs/
legacy/crewai-prototype/          the earlier prototype, kept for reference
```

---

## Stage 1 · Members, commerce, library, search

| Need | Source | How | Take | Target | Licence |
| --- | --- | --- | --- | --- | --- |
| Stripe events, subscriptions, Checkout | `stripe` Python SDK | Dependency | Webhook signature check, typed objects | `platform_api/commerce/adapters/stripe_*.py` | MIT |
| Desk package skeleton: one service layer, recorded samples, behaviour tests | `substack-gateway-oss` | Port | `pyproject.toml` layout; `packages/gateway_core/` (`client/base.py`, `auth.py`, `substack.py`); `packages/gateway_oss/samples/` and the feature tests as the model for `contracts/` | `packages/substack-desk/src/substack_desk/core/`, `contracts/` | MIT |
| Polite client: rate limit, retry, classifying failures (including "schema drift") | `substack-cli-ts` | Port (TypeScript to Python) | `src/substack-api/rate-limit.ts`, `retry.ts`, `mutation-outcome.ts` | `substack_desk/core/ratelimit.py`, `retry.py`, `outcome.py` | Apache-2.0 |
| Subscriber look-up through the official Publisher API | `dkships/substack-publisher-mcp` (not a fork; found in research) | Pattern | Endpoint list and response fields; verify against the owner's own dashboard first | `substack_desk/subscribers/publisher_api.py` | Check before reading closely |
| Subscriber CSV parsing | `substack-mcp` | Port (JavaScript to Python) | `src/api/substack/csv.js` | `substack_desk/subscribers/csv_import.py` | MIT |
| Keyword ranking | `rank-bm25` | Dependency | – | `platform_api/content/search.py` | Apache-2.0 |
| PDF text | `pypdf` | Dependency | – | `platform_api/content/sources/library.py` | BSD |
| Passage quality metrics for tuning the splitter | `adaptive-chunking` | Port | `src/adaptive_chunking/metrics.py` | `platform_api/content/chunking_metrics.py` (dev-only use) | MIT |
| Structured data, catalogue pages, AI-search readiness | `marketingskills` | Skill | `skills/schema`, `skills/ai-seo/references/*`, `skills/programmatic-seo` | Loaded by the coding agent when building `/library` pages | MIT |
| Workspace and catalogue UI components | `magicui` | Dependency | Components through the shadcn CLI | `apps/web/app/components/` | MIT |
| Site theme as a spec; UI quality gate | `design.md`, `impeccable`, `hallmark` | Tool | `export --format css-tailwind`; `npx impeccable detect`; `/hallmark audit` | CI and developer use | Apache-2.0, Apache-2.0, MIT |
| Secret, code and image scanning | `trufflehog`, `semgrep`, `trivy` | Tool | `--only-verified`; CE rules plus a custom rule "no email-shaped literals in tests"; `trivy fs`, `trivy image` | `.github/workflows/security.yml` | AGPL-3.0 (run only), LGPL-2.1, Apache-2.0 |
| Privacy notice, impact assessment, data-request procedure drafts | `claude-for-legal` | Skill | `privacy-legal/skills/pia-generation`, `dsar-response` | Drafts for the owner and her adviser; not in the repo | Apache-2.0 |
| Singapore statute citations for those drafts | `sg-eli-mcp` | Tool | Run the server | Developer use | Apache-2.0 |

Nothing is borrowed for the entitlement engine, the webhook pipeline or the Payhip integration: they are small, specific to this platform, and specified in pages 02 and 03.

## Stage 2 · Gateway, agent teams, Substack Desk, store

| Need | Source | How | Take | Target | Licence |
| --- | --- | --- | --- | --- | --- |
| Model routing, fallbacks, price table | `litellm` | Dependency (container, **pinned by digest, signature verified**) | Proxy in configuration-file mode; custom callback for spend rows | `services/model-gateway/` | MIT (enterprise folder excluded) |
| Calling the gateway from Genkit | `@genkit-ai/compat-oai` | Dependency | `openAICompatible({ name, apiKey, baseURL })` | `agents/shared/gateway.ts` | Apache-2.0 |
| Agent-to-agent protocol | `A2A` | Dependency | `@a2a-js/sdk`, `a2a-sdk`; one agent card per team | `agents/<team>/card.json` | Apache-2.0 |
| Approval gates | `adk-python`, `agentrun`, `pydantic-ai` | Pattern | ADK `ToolConfirmation`; agentrun approval and spend-cap semantics; pydantic-ai deferred tools and `tool_approval.py` | `agents/shared/approvals/` and `platform_api/admin/proposals.py` | Apache-2.0, Apache-2.0, MIT |
| Spend table design | `adk-python` | Pattern | `plugins/bigquery_agent_analytics_plugin.py` | `ops_ai.calls` schema | Apache-2.0 |
| Reviewer loops and rubrics | `deepagents`, `elephant-goldfish-model`, `gstack`, `mini-harness` | Port (prompts), Pattern (code) | `middleware/subagents.py`, `rubric.py`; review-loop standards; review and QA prompts; goal mode with a fresh-context reviewer | `agents/shared/review/` | MIT, Apache-2.0, MIT, MIT |
| Writing checks | `humanizer`, `no-ai-slop` | Skill | `SKILL.md`, `scripts/validate-package.py`; `skills/no-ai-slop/SKILL.md`, `eval.md` as the regression set | `agents/shared/writing-checks/` | MIT |
| Prompt regression tests; answer-with-sources quality | `promptfoo`, `ragas` | Dependency | Test suites in CI | `agents/**/evals/` | MIT, Apache-2.0 |
| Subscriber roster through private endpoints (optional, off by default) | `substack-mcp` | Port (JavaScript to Python) | `src/api/substack/SubstackApi.js`, `SubscriberQuery.js` | `substack_desk/subscribers/private_api.py` | MIT |
| Drafts, publish, schedule, images | `python-substack` (the owner's fork) | Port | `substack/api.py`, `post.py`, `mdrender.py`, `nodes.py`, `mdexport.py` | `substack_desk/posts/` | MIT |
| Markdown conversion, tables and covers as images, overwrite guard | `substack-cli-publishing` | Port | **Read `docs/api-notes.md` first.** `substack_cli/md2pm.py`, `pm2md.py`, `tables.py`, `covers.py`, `posts.py` (audit guard) | `substack_desk/posts/` | MIT |
| Audience flag and paywall node | `substack-mcp` | Port | `src/api/substack/document.js`, `src/tools/update_draft.js` | `substack_desk/posts/paywall.py` | MIT |
| Notes; comments | `substack-gateway-oss`, `substack-mcp` | Port | `gateway_notes*`, `gateway_comments*`; `comment.js` | `substack_desk/notes/`, `comments/` | MIT |
| Statistics | `substack-mcp` | Port | `src/tools/get_analytics.js`, `get_post_stats.js` | `substack_desk/stats/` | MIT |
| Publish preflight, scheduling freeze | `substack-cli-ts` | Pattern | `src/publish/preflight.ts`, `src/policy/scheduling-freeze.ts` | `substack_desk/posts/preflight.py` | Apache-2.0 |
| Novelty gate, voice anchoring by retrieving past posts | `Substack-content-engine` | Pattern (**ideas only, no code: unlicensed**) | Similarity thresholds for "have I already said this"; queue-then-publish | `agents/publishing/` | None |
| Social and web listening for scouts | `last30days-skill-research-topic-public-platforms` | Port | `scripts/lib/` adapters (`reddit_rss.py`, `hackernews.py`, `youtube_yt.py`, `threads.py`, `bluesky.py`, `arxiv.py`), `dedupe.py`, `fusion.py`, `rerank.py`, `relevance.py` | `services/tools-py/scouts/` | MIT |
| Literature clients | `science-skills` | Port | `pubmed_api.py`, `openalex_cli.py`, `clinical_trials_api.py`, `europepmc_api.py` | `services/tools-py/literature/` | Apache-2.0; data sources have their own terms |
| Paper look-up, review and citation habits | `scientific-agent-skills` | Skill | `skills/paper-lookup`, `literature-review`, `citation-management` | `agents/publishing/skills/` | MIT |
| Crawling pages into Markdown | `crawl4ai` | Dependency | Show the required attribution string | `services/tools-py/` | Apache-2.0 with attribution |
| Social, content, community, copy-editing know-how | `marketingskills` | Skill | `skills/social`, `content-strategy`, `community-marketing`, `copy-editing`, `lead-magnets` | `agents/marketing/skills/` | MIT |
| Keyword research and audits | `open-seo-marketing-tool` | Skill | `.agents/skills/keyword-research`, `keyword-clustering`, `seo-audit` | `agents/marketing/skills/` | MIT |
| Instagram and Threads posting | Meta's own APIs | – | Written to the documentation; no library | `agents/shared/social/` behind `SocialPublisher` | – |
| Figures and result cards | `ui-ux-pro-max-skill`, `dimensional-drawing` | Skill | `data/charts.csv`; `SKILL.md` | `agents/publishing/designer/` | MIT |
| Style-rewriter fine-tune | `unsloth` | Dependency (notebook) | QLoRA recipe | Private notebook, not this repo | Apache-2.0 |

## Stage 3 · First survey, consent, research data

| Need | Source | How | Take | Target | Licence |
| --- | --- | --- | --- | --- | --- |
| k-anonymity, l-diversity, t-closeness checks and application | `pyCANON`, `ANJANA` | Dependency | – | `packages/consent-deid/` release gate | Apache-2.0 |
| Removing names and contact details from free text | `presidio` | Dependency | Analyzer and anonymizer; add custom recognisers | `packages/consent-deid/scrub.py`; also the comment-theme pipeline | MIT |
| Consent record vocabulary | ISO/IEC TS 27560, FHIR Consent, GA4GH DUO | Pattern (standards) | Field names, export shape, use codes | `packages/consent-deid/models.py` | – |
| Policy, module, template model for consent | gICS (Greifswald) | Pattern | The three-level model only | `packages/consent-deid/` | AGPL: read, do not copy |
| Sample size and study design reasoning | `scientific-agent-skills` | Skill | `skills/statistical-power`, `experimental-design` | `agents/study-design/skills/` | MIT |
| Personality companion scale | IPIP items | Data | IPIP-NEO-120 or Mini-IPIP item text and keys | `instruments/ipip/` | Public domain |
| Statute citations for consent texts | `sg-eli-mcp` | Tool | – | Developer use | Apache-2.0 |
| Consent page, exit on every page, final confirmation, participant-held code | BPS *Ethics guidelines for internet-mediated research* (2021) | Pattern (guideline) | The behaviours, as engine blocks | `packages/study-governance/blocks/` | – |
| Accessible consent and survey wording for autistic adults | AASPIRE practice-based guidelines (Nicolaidis et al. 2019) | Pattern (guideline) | The checklist the accessibility reviewer applies | `packages/study-governance/checklists/accessibility.md` | – |
| Reporting a web survey | CHERRIES checklist | Pattern (checklist) | Item names; filled from engine counts | `packages/study-governance/reporting/web_survey.yaml` | – |
| Linking anonymous waves | Self-generated identification codes (published methods) | Pattern | Element choice, tolerant matching, link-quality flag | `services/research-api/` linkage module | – |
| One response per member without knowing which member | RSA blind signatures (RFC 9474); Privacy Pass (RFC 9576 to 9578) as the model for issue-and-redeem | Pattern, then a Dependency chosen and independently checked in the Stage 3 plan | The protocol shape | `services/research-api/` participation token | – |

## Stage 4 · Ops team

| Need | Source | How | Take | Target | Licence |
| --- | --- | --- | --- | --- | --- |
| Ops team design: triggers, tickets, mandates, authorisation | `dsh-superagent-prototype` | Pattern | `docs/000-philosophy.md` to `007-architecture.md`, especially 002 and 003 | `agents/ops/` design doc | MIT |
| Fixer agent | `mini-swe-agent` | Dependency | `agents/default.py` with the docker environment, in a Cloud Run job | `agents/ops/fixer/` | MIT |
| Ops agents with confirmation and evaluation | `adk-python`, `agents-cli` | Dependency (ops team only) | `ToolConfirmation`; `eval run`, `eval grade` | `agents/ops/` | Apache-2.0 |
| Policy engine for what agents may do | `agent-governance-toolkit` | Dependency | `PolicyEngine`, `default-policy.json`, the GitHub action | `agents/shared/policy/` | MIT |
| Checking a skill before installing it | `SkillSpector` | Tool | CLI | CI | Apache-2.0 |
| Periodic security audit | `security-audit-skill` | Skill | `skills/security-audit/` with `report-schema.json` | `agents/ops/skills/` | MIT |
| Synthetic journeys and screenshots | Playwright | Dependency | Plain Playwright in a scheduled job | `agents/ops/sentinel/` | Apache-2.0 |
| Post-deploy probe of own routes | `nuclei` | Tool | Custom templates | CI | MIT |

## Stages 5 and 6 · Analysis, synthesis, graph

| Need | Source | How | Take | Target | Licence |
| --- | --- | --- | --- | --- | --- |
| Loop state and delta | `AutoResearch/autora-core` | Port (pattern plus tests) | `src/autora/state.py`: the merge policy and the doctest cases | `packages/research-loop/src/research_loop/state.py` | MIT: keep the notice if code is copied |
| Synthetic respondents with a planted pattern | `AutoResearch/autora-synthetic` | Pattern | Ground-truth runner idea | `packages/research-loop/synthetic.py` | MIT |
| Pattern to hypothesis | `ChicagoHAI/hypothesis-generation` (HypoGeniC); `scientific-agent-skills` `skills/hypogenic` | Pattern, Skill | The generate-and-refine loop | `agents/synthesis/` | MIT |
| Checking a pattern against papers with citations | `Future-House/paper-qa` | Dependency (candidate; evaluate first) | – | `services/tools-py/literature/` | Apache-2.0 |
| Read-only SQL guard for "ask the data" | `auto-ontology-mcp` | Port | `src/auto_ontology_mcp/sqlcheck.py` and the answerable → context → validate → run flow | `services/research-api/.../sqlguard.py` | Apache-2.0 |
| Conflicts, duplicates, provenance in the graph | `semantica` | Port (selected) | `semantica/conflicts/*`, `deduplication/*`, `provenance`, `ontology/competency_questions.py` | `services/research-api/.../graph/` | MIT |
| Extracted versus inferred edges | `graphify` | Pattern | The distinction and how it is stored | Graph schema | – |
| Mapping labels to ontology ids | `scientific-agent-skills` | Skill | `skills/ontology-term-resolution` | `agents/synthesis/skills/` | MIT |
| Tracking analysis runs behind each pattern | `mlflow` | Dependency | File-based tracking in a bucket, no server | M6 notebooks and jobs | Apache-2.0 |
| Cited answers over a full-text corpus | `lawplain` | Pattern (**ideas only: unlicensed**) | Loop design, saving threads by URL | `agents/synthesis/` | None |
| Adaptive item selection, if wanted later | `catsim` | Dependency (later) | – | M3 | BSD-3-Clause |

## Building with agents (tools for the build, not parts of the product)

Reviewed on 2026-11-19 from the owner's newer forks. None is needed to start the Stage 1 build; the build uses Claude Code's own subagents and sessions ([swarm plan](../plans/stage-1-swarm-build-plan.md)).

| Need | Source | How | Take | When | Licence |
| --- | --- | --- | --- | --- | --- |
| See where a lane's time and tokens go | `harness-profiler` | Tool | Its Claude Code hook, which records tool calls and draws the sequence of skills, subagents and contexts | Optional from Wave 2, on one lane first | MIT |
| Read long files and papers with fewer tokens | `SparseReading` | Tool | Its reading layer for coding agents | Optional; first for the literature agents of Stage 2 | MIT |
| A second opinion from another vendor's coding agent | `AutoSwarm` | Pattern, optional Tool | Its hand-off of approvals between agents (`approvals.py`) and small atomic records (`records.py`) as a model for the approval kit; the tool itself only if a cross-vendor reviewer is wanted | Later | MIT |
| Tool servers for agents and for Desk's optional server | `python-sdk` (Model Context Protocol), `servers` | Dependency | The SDK; reference servers as examples | Stage 2 | MIT (the reference servers are moving to Apache-2.0) |
| Scoring agent and retrieval answers | `trulens`, `uaef` | Tool (candidates) | Metric definitions; compare with the evaluation tools already listed for Stage 2 before adding one | Stage 2 spike | MIT; Apache-2.0 |
| Synthetic browser journeys for the ops team | `browser-use` | Dependency (candidate) | Scripted journeys through sign-in and download | Stage 4; Playwright alone may be enough | MIT |
| Retrieval with no model calls | `SAG-Wiki` | Pattern | Its index and retrieval design, as a comparison point for the keyword side of search | S1.7 | MIT |
| Semantic graphs and property graphs side by side | `one-graph-two-worlds` | Pattern (reading) | The mapping between the two models, for the graph store's exit path | Stage 5 | MIT (code) |

## Reviewed and not used

| Candidate | Why not |
| --- | --- |
| Postiz | Needs a database, a cache and a workflow engine running permanently; two channels do not justify it |
| Langfuse, self-hosted | Six moving parts; traces go to Cloud Trace at no cost instead |
| AutoRA as an installed dependency | Dormant core, old NumPy pin, in-process loop, pickled raw data; the design is ported instead |
| gICS, gPAS, E-PIX, Mainzelliste | Complete but heavy and AGPL; built for hospital trust offices |
| REDCap | Not open source; licensed only to institutions |
| firecrawl, wigolo (self-hosted) | AGPL services; crawl4ai covers the need |
| Cloud SQL for the gateway | Only if the Stage 2 spike shows the caps cannot be enforced without it |
| `substack-cli-ts` advanced endpoints | Mostly guesses; only its client utilities are taken |
| `substack-blog-automation` | Never calls Substack; nothing to take |
| `PageLM`, `mirror`, `GenAI_Agents`, Rust `substack-cli` | Non-commercial, layered or missing licences; nothing needed from them |
| `E2B` | Sandboxes for agents. Cloud sessions and Cloud Run jobs already isolate the work; a second sandbox vendor adds a processor |
| `phoenix` | A trace screen under the Elastic License 2.0; traces already go to Cloud Trace at no cost |
| `OmniRoute` | Stacks third parties' free tiers behind one gateway. Not for anything that carries members' data; the gateway decision stands ([ADR 0011](../adr/0011-self-hosted-model-gateway.md)) |
| `ci` (a time-series forecasting model) | Custom licence with attribution and notification duties; revenue forecasting is not needed before Stage 2 and simpler methods come first |
| `minimind`, `openai-cookbook`, `system-design-academy`, `fastapi` (already a dependency) | Learning material or already in use |
| `codex`, `qwen-code` | Other vendors' coding agents; only relevant through `AutoSwarm`, above |
| `claude-code` (the vendor's repository) | All rights reserved: examples to read, nothing to copy |
| `craft-anything` | Site cloning; not relevant |

## `THIRD_PARTY.md` entry format

```markdown
| Target path | Source repository and commit | Source path | Licence | How | Changes | Release note |
| --- | --- | --- | --- | --- | --- | --- |
| packages/substack-desk/src/substack_desk/core/retry.py | edithatogo/substack-cli-ts @ abc1234 | src/substack-api/retry.ts | Apache-2.0 | Port (TS to Python) | Rewritten for httpx; same back-off rules | OK to release with notice |
```
