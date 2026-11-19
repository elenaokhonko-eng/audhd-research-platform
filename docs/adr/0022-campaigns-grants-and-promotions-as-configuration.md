# ADR-0022: Launch grants and promotions are configuration; promotions name the channel where money changes hands; reconcile by polling before webhooks

**Status:** Proposed
**Date:** 2026-11-19
**Deciders:** Owner (Elena Okhonko)

## Context

The owner wants each existing paid subscriber to receive paid platform access for a set period, and wants a time-boxed discount on the annual plan during a sales season. The terms (months, percentage, dates) are hers to set and may change per season. The repository is public. The Stage 1 design has Stripe webhooks and a platform checkout, neither of which exists yet, and the first promotion's date is fixed by the calendar.

## Decision

(1) A launch grant is an ordinary `grant` entitlement created by a **grant policy** on a campaign, with a deterministic id per contact and campaign, from verified facts only. (2) A **promotion** is a record with a window, an audience, display text and a **channel**: `substack_offer` now (the owner creates the offer in Substack; the platform links to it and counts upgrades), `platform_checkout` later (a Stripe coupon applied by the server). (3) Campaigns and promotions are written from private configuration files through admin routes; no percentage, price or date is in code or in this repository. (4) Until the webhook path exists, paid status is kept current by a scheduled, read-only reconcile job that applies Stripe's current state, started more often while a campaign is open and on a member's request. Only that job's identity can read the Stripe key. (5) Every paid-status record carries the start date its source reports, so 'paying before the announcement' and 'upgraded during the promotion' are facts and not artefacts of the first import.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Grants and promotions as data; Substack offer first; polling reconcile (chosen) | Low | None | Enough for thousands of subscriptions | Good | No new code touches money; terms change without a deploy; works before webhooks | Access after an upgrade can lag by minutes |
| B. Platform checkout with a Stripe coupon for the first promotion | High | Stripe fees on new sales | Large | Fair | The platform earns directly; exact attribution | New payment code in its first week; price, tax and terms of sale must be settled first |
| C. Hard-coded seasonal promotion | Low | None | – | Poor | Fastest once | Terms in a public repository; a deploy to change a date |
| D. Webhooks before launch | Medium | None | Large | Good | Seconds instead of minutes | More parts to build and operate before the first member arrives; the reconcile is needed anyway as the safety net |

## Trade-off Analysis

A separates the revenue event from the engineering schedule: the Substack offer works with no platform at all. Minutes of delay are acceptable when the page says so and offers 'Check again'. B and D are the next slices, not rejected designs.

## Consequences

- Easier: a new season is a new configuration file.
- Easier: `platform-api` holds no payment credential.
- Harder: until Stripe shows how a Substack offer appears on a subscription, upgrade counts are by date window, not by coupon.
- What a Substack paid subscription includes after the grant period is the owner's commercial decision; the engine supports both answers without change.
- Revisit when: the webhook path ships (the schedule can relax to nightly), and when a platform-only product has a price.

## Action Items

1. [ ] Owner decides the commercial model, the grant terms and the promotion terms (private launch plan)
2. [ ] Implement in the launch track (entitlements and commerce lanes)
3. [ ] Check once, read-only, how a Substack offer appears on a Stripe subscription
