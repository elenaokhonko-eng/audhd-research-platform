# ADR-0007: Stripe is the source of truth for paid status; Substack's own record covers the rest

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Paid Substack subscribers must get paid platform access and lose it automatically when they stop paying. Substack has no webhooks and no general API. It bills readers through the owner's own Stripe account, where its subscriptions are ordinary objects marked with Substack's application id; the account's event log was checked on 2026-11-16 and contains their lifecycle events. Stripe does not see complimentary and gift subscriptions, group seats, or readers billed by Apple. Substack's terms prohibit automated access to its private endpoints.

## Decision

Card-paying subscribers: entitlements follow Stripe webhooks, confirmed by a nightly reconciliation, using a read-only restricted key. Everyone else: a `SubscriberDirectory` port with three adapters in order of preference: Substack's official Publisher API (if the publication has it), an uploaded CSV export, and private endpoints as an optional, switched-off convenience. The platform never changes an object Substack created.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Stripe events plus a directory port (chosen) | Medium | None | Any size | Good | Seconds to react; official data paths; no dependency on private endpoints | Two sources to reconcile |
| B. Poll Substack's private subscriber endpoints | Medium | None | Fine | Risky | One source | Against Substack's terms; breaks without notice; minutes to hours of delay |
| C. CSV upload only | Low | Owner's time | Poor | Simple | Fully official | Downgrades wait for the next upload |
| D. Members prove status themselves (code in a paid post) | Low | None | Fine | Poor experience | No integration | Codes leak; no automatic downgrade |

## Trade-off Analysis

Option A puts the time-critical, money-related path on the one integration that is official, signed and real-time, and leaves only the slow-changing remainder to Substack's own surfaces.

## Consequences

- Easier: automatic upgrade and downgrade; an exit from Substack later without touching entitlements.
- Harder: a reader who pays through Apple or holds a gift is recognised only by the directory, so the first visit can need the link-another-email flow or a manual grant.
- Revisit when: Substack ships webhooks or a member API, or changes how it uses Stripe.

## Action Items

1. [ ] Owner creates the restricted keys and the webhook endpoint with the provided script (S1.3)
2. [ ] Owner checks the dashboard for the Publisher API (S1.4)
