# ADR-0006: One backend service with enforced modules

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Architecture v3 mapped every module to its own Cloud Run service. Stage 1 now builds four modules at once (membership, commerce, library, content index) whose rules must agree with each other at every request: a download is allowed only if an entitlement is live, an entitlement changes when a payment event arrives. There is one developer, traffic is low, and every extra service adds a deploy, an identity, a cold start and a network hop.

## Decision

Stage 1 backend code ships as one container image, `platform-api`, organised as modules with import rules enforced in CI (import-linter). A module may use another only through its `public.py`. The same image also runs as `platform-hooks` (public, webhook routes only) and as Cloud Run jobs. A separate deployable is created only for a different trust level (webhooks), a different data zone (`research-api` in Stage 3), or a different runtime (the website, the model gateway, agent teams).

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. One service per module (v3) | High | Low, but many cold starts | Each module alone | Poor for one developer | Hard isolation; independent scaling | Cross-module rules need distributed consistency; five deploys to change one flow |
| B. Modular monolith (chosen) | Low | Lowest | One instance class for all | Good | One deploy, one transaction, simple local runs; boundaries still enforced | One blast radius; needs discipline, hence the lint |
| C. A function per endpoint | Medium | Low | Per function | Poor | Fine-grained scaling | Shared rules scattered; hardest to test |

## Trade-off Analysis

The benefit of separate services is independent scaling and failure isolation. Neither is needed at a few requests per second, while consistency of entitlement decisions is needed from the first day. Enforced module boundaries keep the option to split later at low cost.

## Consequences

- Easier: local development, tests, deploys, reasoning about a request end to end.
- Harder: a fault in one module can take the API down; mitigated by small scope and health checks.
- Revisit when: more than about 20,000 members, a second developer, or one module needs very different scaling.

## Action Items

1. [ ] Add `.importlinter` contracts in slice S1.0
2. [ ] Document `public.py` as the only cross-module entry in `CLAUDE.md`
