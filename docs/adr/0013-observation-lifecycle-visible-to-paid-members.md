# ADR-0013: Exploratory observations are visible to paid members, labelled

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

v3 kept patterns from the platform's own data visible only to the owner until written up. The owner wants paid members to see them in Ask AuDHD Research with their level, a lower weight and filters, wants the book to draw on all levels, and wants PhD proposals to use only replicated or better.

## Decision

Five levels: exploratory, reported, replicated (preregistered and confirmed on fresh data), preprint, published. Each observation shows its level wherever it appears. Paid members see all five by default with a filter and an explanation. Default weights are configuration and are described as a reading aid. Guard rails before a level 1 or 2 observation is visible: 30 or more respondents per group, no cell under 5, an effect size with interval, no treatment or causal wording, owner approval, consent that covers reporting aggregates to members.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Owner-only until reported (v3) | Low | None | – | Safe | No risk of over-reading | Members get nothing from the data they contributed until an article exists |
| B. Visible with labels, weights and guard rails (chosen) | Medium | None | – | Good | Members see early signals with honest framing; a reason to stay paid | Risk of over-reading; needs wording rules and approval |
| C. Visible without labels | Low | None | – | Poor | Simplest | Indistinguishable from evidence; not acceptable |

## Trade-off Analysis

B trades a controlled risk of misreading for member value, and controls it with labels, thresholds and a human approval.

## Consequences

- Easier: showing the research loop working; recruiting for replication surveys.
- Harder: every observation needs approval and a sample description.
- Revisit when: the first replication succeeds or fails, to check the weights and wording.

## Action Items

1. [ ] Add `config/platform/evidence_weights.yaml` in Stage 5
2. [ ] Write the level explanations with the owner
