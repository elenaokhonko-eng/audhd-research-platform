# ADR-0009: Substack Desk is a package in this repository, built to be lifted out

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

The owner wants Substack management built inside the platform first and possibly open-sourced later. It talks to private endpoints that change, so it needs its own tests against recorded responses. The rest of the platform should not care which newsletter provider is behind it.

## Decision

`packages/substack-desk` is a standalone Python package with no imports from the platform. It reaches the outside through ports (credentials, events, blobs, key-value state, clock) that the platform implements. CI installs and tests it alone. Platform modules depend on narrow ports (`SubscriberDirectory` in Stage 1, `NewsletterPublisher` from Stage 2). Every capability is a switch in a capability matrix.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Separate repository now | Medium | None | n/a | Premature | Clean separation | Slows change while the design is still moving; a release process to maintain |
| B. Package in the monorepo with enforced isolation (chosen) | Low | None | n/a | Good | One pull request changes Desk and its users; extraction is a folder move | Isolation must be enforced by lint and CI |
| C. Substack code inside platform modules | Lowest | None | n/a | Poor | Fastest start | Cannot be extracted; private-API churn leaks everywhere |

## Trade-off Analysis

B gives the speed of one repository and the separation of two, at the price of two CI checks.

## Consequences

- Easier: later open-sourcing; swapping the newsletter provider.
- Harder: adapters for platform services live outside the package and must be kept in step.
- Revisit when: the package has outside users, at which point it moves out.

## Action Items

1. [ ] Create the skeleton and both CI checks in S1.4
2. [ ] Record every ported file in `THIRD_PARTY.md`
