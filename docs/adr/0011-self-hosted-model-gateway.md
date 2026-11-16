# ADR-0011: A self-hosted model gateway and no paid observability tool

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Six agent teams will call language models. The owner wants to change models and providers freely, to see and cap spend per team, and to pay no fixed monthly fee for tooling. LiteLLM's proxy runs from a configuration file without a database but needs PostgreSQL for its own keys, budgets and admin screens. Its published packages were compromised twice in 2026. Langfuse self-hosting needs six components.

## Decision

Run the LiteLLM proxy as a private Cloud Run service in configuration-file mode, from an image pinned by digest with its signature verified. Agents request a task tier, not a model. A callback writes one spend row per call to BigQuery and enforces a daily cap per team. Traces go through OpenTelemetry to Cloud Trace. Prompt and answer quality are tested with promptfoo and ragas in CI. No database and no Langfuse. Stage 2 opens with a spike that must prove routing, caps, spend rows and keyless Vertex access before agents are built.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Each agent calls providers directly | Low | None | Fine | Poor | Nothing to run | No single place for caps, logs or model swaps; keys spread across teams |
| B. LiteLLM proxy, configuration-file mode, pinned (chosen) | Medium | About zero | Fine | Good | Provider portability, fallbacks, one egress point, no database | Caps and spend need our own callback; supply-chain care |
| C. LiteLLM with PostgreSQL | Medium | About US$14 a month | Fine | Good | Native keys, budgets, admin screens | First always-on cost |
| D. A hosted gateway service | Low | Usage fees | Fine | Good | Nothing to run | Prompts leave the project; another vendor |
| E. A thin gateway of our own | Medium | About zero | Fine | Good | No third-party supply chain | Re-implements provider translation |

## Trade-off Analysis

B meets the cost goal and portability with the least code. C and E are the named fallbacks if the spike shows caps cannot be enforced cleanly.

## Consequences

- Easier: changing models; a weekly spend report by team and task.
- Harder: upgrades are deliberate pull requests with signature checks.
- Revisit when: teams need per-key self-service or the admin screens, which is the case for option C.

## Action Items

1. [ ] Stage 2, first task: gateway spike with four acceptance tests
2. [ ] Pin the image digest in Terraform; add the signature check to CI
