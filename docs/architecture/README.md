# Architecture v4

**Status:** v4 approved by merge on 2026-11-17 · v4.1 additions proposed for the owner's review · 2026-11-19
**Rule:** no Stage 1 code is written until the launch design, the contracts and the swarm build plan are approved.

**What v4.1 adds:** a launch track at the front of Stage 1 (one join link per audience, recognition by verified email, launch grants, promotions shown from Substack); study governance (study packs, ethics policy as code, ethics and survey templates that agents fill); a plan to build Stage 1 with parallel lanes of Claude agents; a review of the owner's newer forks.

Stage 0 (the site on Cloud Run) is live. v4 reorders everything after it: members, payments and the paid library first; then publishing, marketing and revenue automation; then data collection; then the ops team, analysis, the evidence graph, and the PhD and book work.

## Read in this order

| # | Page | Answers |
| --- | --- | --- |
| 01 | [System overview](01-system-overview.md) | What exists, what runs where, how modules talk, the design rules |
| 02 | [Membership and entitlements](02-membership-and-entitlements.md) | Who may open what, and how that follows Substack and Stripe automatically |
| 03 | [Commerce and revenue](03-commerce-and-revenue.md) | Stripe, Payhip, the later store, the revenue picture, the owner cockpit, the Revenue team |
| 04 | [Content library and search](04-content-library-and-search.md) | Publishing PDFs, gated downloads, one index for everything |
| 05 | [Substack Desk](05-substack-desk.md) | The extractable Substack package, its risks, the change feed, the sentinel, Notes, comments |
| 06 | [AI platform and agent teams](06-ai-platform-and-agent-teams.md) | Model gateway, voice, approvals, the six teams, cost |
| 07 | [Research loop and evidence](07-research-loop-and-evidence.md) | The loop, five evidence levels, consent, instruments, the survey template agent |
| 08 | [Security, identities and organisation](08-security-identities-and-org.md) | Folder and projects, service identities, secrets, threats, the pre-launch checklist |
| 09 | [Events and data model](09-events-and-data-model.md) | Zones, collections, tables, events, ids, retention |
| 10 | [Borrow map](10-borrow-map.md) | What to reuse from which repository, into which path |
| 11 | [Study governance and survey templates](11-study-governance-and-survey-templates.md) | How studies of this kind are run, the study pack, ethics templates, the rules the survey engine enforces, survey blueprints |

Then: [roadmap](../plans/roadmap.md) · [Stage 1 plan](../plans/stage-1-members-and-commerce.md) · [launch design](../superpowers/specs/2026-11-19-launch-invites-grants-promotions-design.md) · [contracts](../contracts/stage-1-launch.md) · [swarm build plan](../plans/stage-1-swarm-build-plan.md) and its [operating manual](../swarm/README.md) · [first slice, task by task](../superpowers/plans/2026-11-16-stage-1-slice-0-platform-skeleton.md) · [decisions](../adr/) · [research briefs](../research/).

## Diagrams

Every page carries its diagrams as Mermaid, which GitHub renders. The index:

| Diagram | Page |
| --- | --- |
| Context: people, platform, outside services | 01 §3 |
| Module map by stage | 01 §4 |
| What runs after Stage 1 | 01 §5 |
| Entitlement states | 02 §4 |
| First sign-in of a paid subscriber; non-renewal | 02 §5 |
| Stripe backfill; webhook path; Payhip purchase | 03 §3, §4 |
| Publishing a library item; the search index | 04 §2, §3 |
| Substack Desk boundaries; sentinel; Notes pipeline | 05 §2, §5, §6 |
| Gateway and teams | 06 §1 |
| Research loop; survey template agent | 07 §1, §6 |
| Folder, projects, later organisation | 08 §1 |
| Zones; Zone 1 entity relationships | 09 §1, §2 |
| Stages | roadmap |
| The join flow | launch design §5.2 |
| Who prepares and approves a study pack | 11 §3 |
| Waves and gates of the build | swarm build plan §4 |

## What is not in this repository

This repository is public. The following stay in the private project notes: the ethics and governance brief, the review of commercial type instruments, the instrument licence list, pricing decisions, the terms of launch grants and promotions (percentages, lengths, dates), filled study packs, subscriber numbers, account identifiers, and all research content (`docs/content-model.md`).

## Superseded

`docs/ARCHITECTURE.md` describes the 2026 CrewAI prototype and is kept only as history. Where it disagrees with this folder, this folder is right.
