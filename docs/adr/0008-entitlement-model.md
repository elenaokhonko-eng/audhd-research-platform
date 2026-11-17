# ADR-0008: Access is the union of entitlement records, never a stored tier

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Access comes from five sources that start and stop independently: Substack through Stripe, Substack's roster, the platform's own Stripe sales, Payhip purchases and owner grants. The channel a person came through must be preserved even when their access changes.

## Decision

Each grant of access is one `entitlement` record: who (contact), what (`tier:paid` or `item:<sku>`), source, source reference, access scope, validity, status. Effective access is computed as the union of live records. Ids are deterministic so repeated events are harmless. Each source may end only its own records. Three fail-safe rules apply: verify at the source before expiring, never mass-expire on one run, never grant without a verified event. A date prompts a re-check and does not end access by itself. The platform applies the source's current state, fetched when an event arrives, not the event's contents. A verified sign-in claims waiting entitlements, and a claim stays with that member. People are stored as `contacts` with a map of channels, separate from registered `members`.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. A tier field on the user, updated by sync jobs | Low | None | Fine | Familiar | Simple reads | Sources overwrite each other; no history; cannot express single-item purchases or grants |
| B. Entitlement records with derived access (chosen) | Medium | None | Fine | Good | Every access decision is explainable; sources independent; items and tiers alike | A query per decision (a handful of documents) |
| C. Stripe's own entitlements feature or an entitlements service | Low to start | Fees or lock-in | Fine | Partial | Less code | Cannot cover Payhip, complimentary and Apple-billed readers or owner grants; would require editing Substack-created products |

## Trade-off Analysis

B costs a small query on each gated request and buys independence of sources, an audit trail and one mechanism for tiers, single items, bundles and report purchases.

## Consequences

- Easier: answering 'why does this person have access'; adding ResearchPro tiers and report purchases later.
- Harder: nothing may cache a tier for long; the session carries identity only.
- Revisit when: entitlement reads exceed a few hundred per second.

## Action Items

1. [ ] Implement in S1.2 with the rules as pure functions under test
