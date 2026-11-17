# ADR-0017: Voice: style guide and retrieved examples first, a tuned rewriter later

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Agents must write in the owner's voice. Her pre-AI writing exists as Substack posts and in email. She wants to learn fine-tuning on a small open model and asked whether her own model can run on Google Cloud. Frequent prompt edits cause drift.

## Decision

Stage 2: build a corpus from her Substack posts (email only by her selection, cleaned), extract and hand-edit a style guide, and add the most similar passages of her own writing to each drafting prompt. Later: LoRA-tune a small open model as a style rewriter on pairs of plain paraphrase and her original, serve it on a Cloud Run GPU that sleeps when unused, and register it in the gateway. Guard against drift with versioned prompts, a fixed reference set re-drafted on every change, and a monthly comparison with the corpus.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Style guide plus retrieved examples (chosen first) | Low | A few dollars a month | Fine | Good | Works on day one; easy to inspect and correct | Voice lives in the prompt; long drafts can wander |
| B. Tune a Google model inside Vertex AI | Low | About US$15 once, little to run | Fine | Fine | Cheapest tuned option | Weights stay with Google; little to learn; not portable |
| C. LoRA style rewriter on a small open model (chosen second) | Medium | Free to train on a notebook GPU; a few dollars a month if batched | Fine | Good | Portable weights; a real fine-tuning project; restyles checked text so it cannot add facts | A GPU service to operate; cold starts |
| D. A fully tuned author model | High | Higher | Fine | Poor | One model does everything | Mixes facts and style; hardest to keep honest |

## Trade-off Analysis

A gives most of the benefit immediately. C is added as a contained learning project whose failure cannot harm content accuracy, because it only rewrites style.

## Consequences

- Easier: every writing agent shares one voice asset.
- Harder: the corpus is personal data and stays in a private bucket.
- Revisit when: the reviewer's voice scores plateau, which is the signal to start C.

## Action Items

1. [ ] Owner selects the corpus sources (Stage 2)
2. [ ] Create the reference set of twenty briefs
