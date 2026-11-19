# CLAUDE.md: working in this repository

You are helping build **audhdneurobiology.org**: a member platform for a research newsletter, on Google Cloud. Read this file fully before changing anything.

## What this repository is, and is not

- It is **public**. Everything committed here is published.
- It holds platform code, infrastructure, tests, architecture docs and plans.
- It never holds: research content, article drafts, PDFs, real people's data, emails, account or provider ids, subscriber numbers, prices under discussion, secrets. Private research lives in a sibling folder read through `AUDHD_CONTENT_DIR` (`docs/content-model.md`). If that variable is missing, stop; never fall back to a folder inside this repository.
- `ops/scripts/check-private-content.sh` runs before each commit and in CI. Do not weaken it.

## Where the design lives

| Read | For |
| --- | --- |
| `docs/architecture/README.md` and pages 01 to 11 | The design. Page 01 first. |
| `docs/adr/` | Why each decision was made. Add an ADR when you change one. |
| `docs/plans/roadmap.md` | Stage order and exit tests |
| `docs/plans/stage-1-members-and-commerce.md` | The current stage, slice by slice |
| `docs/superpowers/specs/` | The design of a single feature, approved before its plan is written. Current: the launch track |
| `docs/contracts/` | Names and shapes that parallel lanes share: routes, functions, documents, events, settings. Build exactly what it says; change it only through a pull request labelled `contract-change` |
| `docs/plans/stage-1-swarm-build-plan.md` and `docs/swarm/` | How Stage 1 is built by parallel lanes: who owns which paths, roles, the rules for a pull request, kick-off prompts |
| `docs/superpowers/plans/` | Task-by-task plans. Implement from these with the `superpowers:executing-plans` or `superpowers:subagent-driven-development` skill. |
| `docs/architecture/10-borrow-map.md` | **Check before writing a component**: what to reuse and from where |

The owner reviews and approves a design and its cost before execution starts. If a plan is missing for the slice you were asked to build, write the plan first (`superpowers:writing-plans`) and stop for review.

## Layout

```
apps/web/                  Next.js site, member workspace, admin (TypeScript)
services/platform-api/     Backend: membership, commerce, library, content index (Python, FastAPI)   [Stage 1]
packages/substack-desk/    Substack integration, extractable; must not import platform_api            [Stage 1 on]
packages/events/           Event schemas shared by Python and TypeScript                              [when needed]
packages/study-governance/ Study pack schemas, rules, ethics and survey templates, extractable         [Stage 3; templates earlier]
agents/                    Genkit agent teams                                                         [Stage 2 on]
infra/terraform/           modules/ and one root per environment under envs/
ops/scripts/               Bootstrap and smoke scripts the owner runs in Cloud Shell
docs/                      architecture, adr, plans, research, runbooks
src/ config/ platform_app/ app_pages/ streamlit_app.py   Earlier prototype. Legacy. Do not extend.
```

## Commands

```bash
# website
cd apps/web && npm ci && npm run build

# backend (once services/platform-api exists; see the slice plan for exact commands)
cd services/platform-api && uv sync && uv run pytest -m "not integration" && uv run ruff check . && uv run mypy src && uv run lint-imports

# infrastructure: format and validate only
terraform fmt -check -recursive infra/terraform

# guard
bash ops/scripts/check-private-content.sh
```

## Rules that are not negotiable

1. **Tests first.** Write the failing test, see it fail, then implement. Rules (entitlements, access, events) are pure functions under unit test.
2. **No personal data** in code, tests, fixtures, logs, events, commit messages or docs. Fixtures use invented people at `example.org`. Events carry ids only; `new_event` rejects email-shaped strings and that check must stay.
3. **No secrets, no key files.** Services run as their own service accounts. Secrets live in Secret Manager and are entered by the owner from her terminal. Never ask for a secret in chat; never write one to a file or a CI variable.
4. **Module boundaries.** In `platform_api`, a module uses another only through its `public.py`. `substack_desk` imports nothing from the platform. `lint-imports` must pass.
5. **Entitlements fail safe.** Never remove access on missing information; never mass-expire; never grant without a verified event (`docs/architecture/02-membership-and-entitlements.md` §4).
6. **Read-only towards Stripe objects created by Substack or Payhip.** Never update, cancel or refund them.
7. **Infrastructure is Terraform.** No resource is created by hand. Region is `asia-southeast1`. Public Cloud Run services use `invoker_iam_disabled`, never `allUsers`. Do not use root paths ending in `z` (use `/health`).
8. **Models are called only through the model gateway** (from Stage 2), naming team and task. No provider key in any agent.
9. **Agents propose, people approve.** Anything public or irreversible (publish, post, send, price, deploy, data release) is a proposal until the owner approves it.
10. **Record borrowed code.** Every ported file goes into `THIRD_PARTY.md` in the same pull request, with its source licence header kept (`docs/adr/0012-borrowed-code-provenance.md`).

## What you must never do

- Run `terraform apply`, deploy to production, or merge your own pull request. Applying infrastructure is the owner's step, from the runbook.
- Push to `main`. Work on a branch; open a pull request.
- Call Substack's private endpoints from tests or CI. Tests use recorded responses.
- Touch the live Stripe account from tests. Use a sandbox.
- Copy an API key, token or real response containing personal data out of any source repository.
- Extend the legacy prototype folders.

## Conventions

- **Commits:** imperative, plain sentences, one logical change. Author is the owner's GitHub noreply identity (set in the session). Never commit `terraform.tfvars`.
- **Pull requests:** say what changed, how it was tested, and what the owner must do (if anything) in Cloud Shell.
- **Docs:** when behaviour changes, the page in `docs/architecture/` changes in the same pull request. Diagrams are Mermaid.
- **Writing for the owner:** she is a data and enterprise architect who wants to understand the structure before the code. Explain a term the first time it appears. Prefer commands to console clicks.
- **Python:** 3.12, FastAPI, Pydantic v2, `uv`, `ruff`, `mypy --strict`. **TypeScript:** strict mode.
- **Events:** CloudEvents; type `org.audhdneurobiology.<area>.<thing>.<past-tense verb>`; listed in `docs/architecture/09-events-and-data-model.md` when added.

## When something is unclear

Stop and ask the owner. In particular: anything that would change an ADR, add a fixed monthly cost, switch on a Substack private-endpoint capability, or touch members' data in a way the docs do not describe.

If you were started as a lane of the Stage 1 build, `.claude/rules/swarm.md` and `docs/swarm/README.md` apply as well. They add to this file and never loosen it.
