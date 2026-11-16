# ADR-0016: Post to Instagram and Threads through Meta's own APIs, behind a port

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

The owner runs two social channels: Instagram and Threads. v3 chose Postiz as a self-hosted scheduler. Postiz now requires PostgreSQL, Redis and a workflow engine and several gigabytes of memory, which means an always-on machine. Meta's APIs let an account owner post to her own accounts without app review; tokens last 60 days and can be refreshed.

## Decision

A `SocialPublisher` port with two adapters, Instagram and Threads, calling Meta's APIs directly. A job refreshes tokens. Scheduling is the platform's own queue of approved posts. Postiz is not deployed.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Postiz self-hosted (v3) | High | US$25 to 60 a month | Many channels | Over-sized | One interface for many networks; its AGPL licence permits private modification | Always-on cost and three services to operate for two channels |
| B. Meta APIs behind a port (chosen) | Medium | None | Two channels | Good | No fixed cost; full control | A Meta developer app to maintain; each new network is a new adapter |
| C. A paid scheduling service | Low | A monthly fee | Many channels | Fine | Nothing to build | A fee before there is reach; content leaves the platform's approval flow |

## Trade-off Analysis

With two channels the adapter work is small and removes the largest fixed cost in the v3 estimate.

## Consequences

- Easier: near-zero running cost; posts tied to the approval kit.
- Harder: Meta's publishing rules (image formats, daily limits) are ours to track.
- Revisit when: a third or fourth network is added; Postiz or a paid tool then earns its keep.

## Action Items

1. [ ] Owner creates the Meta developer app and connects both accounts (Stage 2)
2. [ ] Verify one test post is visible when logged out
