# ADR-0019: Evidence graph on Aura Free now, portable to Spanner Graph

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

The owner chose Neo4j Aura Free for the evidence graph for now and requires that it can move to Spanner Graph. The graph is not needed before Stage 5.

## Decision

BigQuery tables of nodes and edges are the system of record. The graph database is a projection rebuilt from them by a job. Callers use an `EvidenceStore` port with named queries; no query language appears outside the adapter. Queries stay within the subset common to openCypher and GQL. Contract tests run the same cases against each adapter.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Aura Free as a rebuildable projection (chosen) | Low | None | Aura Free limits | Good | No cost; switching is a rebuild | A service outside Google; free-tier limits and pauses |
| B. Spanner Graph from the start | Medium | About US$65 to 90 a month | Large | Good | All on Google; no migration | A fixed cost a stage before any paying graph user |
| C. BigQuery only | Low | None | Fine for batch | Fine | Nothing new to run | Slow for interactive multi-hop questions |

## Trade-off Analysis

A defers the largest optional cost until ResearchPro revenue exists, and the projection design makes the later move mechanical.

## Consequences

- Easier: rebuilding after a schema change; moving stores.
- Harder: the graph is eventually consistent with BigQuery.
- Revisit when: Aura Free limits are reached or ResearchPro has paying users.

## Action Items

1. [ ] Define `EvidenceStore` and its contract tests in Stage 5
