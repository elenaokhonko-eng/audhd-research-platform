# ADR-0018: Search: an in-memory hybrid index built from a snapshot, behind a port

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Everything published must be findable in one search, with results filtered by what the reader may open. The corpus is small: a few hundred library items and up to about two thousand articles and pages. Exact terms (drug names, abbreviations) matter as much as meaning. Fixed cost must stay near zero.

## Decision

A job writes a snapshot (passages, vectors, manifest) to a bucket. `platform-api` loads it into memory and ranks by keyword (BM25) and by vector similarity, merged by reciprocal rank fusion, then filters by access. Passages are marked public or gated. All of this sits behind `SearchIndex`, `Embedder` and `ContentSource` ports.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. In-memory hybrid from a snapshot (chosen) | Low | None | About 50,000 passages | Good | Keyword and meaning together; nothing running when idle; snapshot is portable files | Memory grows with the corpus; instances reload on change |
| B. Firestore vector search | Low | None at this size | Larger | Good | No memory cost; filters in the query | Meaning only: no keyword ranking; exact terms rank poorly |
| C. A managed search product | Low | A usage fee | Large | Fine | Least code | Cost before need; less control over access filtering |
| D. PostgreSQL with vectors, or a search server | Medium | An always-on instance | Large | Fine | Mature hybrid search | The first fixed cost, for a few thousand passages |

## Trade-off Analysis

A is the only option that is both hybrid and free while idle at this size. The port makes B, C or D a later adapter.

## Consequences

- Easier: zero-cost search; reproducible snapshots for tests.
- Harder: the API needs about 1 GiB of memory; indexing is a batch, so new items appear within minutes rather than instantly.
- Revisit when: more than about 50,000 passages or 5 searches a second.

## Action Items

1. [ ] Implement in S1.7 with the owner's 30 test questions as the acceptance set
