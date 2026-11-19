# ADR-0023: Every study is a study pack built from templates; the ethics policy is data that the survey engine enforces

**Status:** Proposed
**Date:** 2026-11-19
**Deciders:** Owner (Elena Okhonko)

## Context

The platform will run questionnaire studies with a population that includes vulnerable people, operated by one person with agent help. Current practice expects review before collection, proportionate safeguards, explicit short consent, real anonymity when anonymity is claimed, safeguards for sensitive questions, and reporting to a checklist. v4 already required an ethics route per study and green instruments. The owner asked for pre-built ethics policy templates per study and survey templates that agents configure from a study's objectives.

## Decision

A study is a folder (`study.yaml`, `ethics/`, `survey/`, `analysis/`, `reporting/`) generated from an **archetype** plus **add-ons** in a public template library (`packages/study-governance/`). `ethics.yaml` states the route and its evidence, the collection mode, linkage, consent scopes, sensitive-topic safeguards, retention, release thresholds and required reviews. A pure function, `can_open(pack, now)`, checks the pack against a fixed rule set; it runs in CI, at the command line and inside the survey engine, and the engine's answer is the one that counts. Surveys are composed from **blueprints** (ordered slots) filled with registry instruments, reusable **blocks** and item templates. Study-design agents draft and check; they cannot choose a route, record an approval or open a study. Filled packs are private until published; templates, schemas and rules are public.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Study pack with policy as code (chosen) | Medium | None | Any number of studies | Good | The safeguards cannot be forgotten; packs are reviewable diffs; templates are reusable and publishable | Up-front work on templates and rules |
| B. Documents only, checked by the owner | Low | None | Poor | Fair | Nothing to build | Relies on memory under time pressure; agents have nothing to check against |
| C. Adopt a research data platform's project workflow | High | Hosting or licence | Large | Poor | Mature | The complete open stacks are heavy or licensed to institutions; none ties consent scopes to an instrument licence registry |

## Trade-off Analysis

A puts effort where a single mistake is most costly and least reversible. The rules are small and testable, and they turn the review a committee would do into something an agent can prepare for and a person can verify.

## Consequences

- Easier: the first survey ships by filling a template; later studies reuse blocks and consent text.
- Easier: a committee or adviser receives a consistent pack.
- Harder: a change after opening is an amendment with its own record.
- A template is a drafting aid, not a review; the route and its evidence remain the owner's responsibility.
- Revisit when: a university's own templates must be used; they become another archetype.

## Action Items

1. [ ] Write schemas, rules with tests, archetypes, blocks and blueprints (can start before Stage 3)
2. [ ] Wire the gate into the survey engine in Stage 3
3. [ ] Owner chooses the route for the first study and obtains the written confirmation it rests on
