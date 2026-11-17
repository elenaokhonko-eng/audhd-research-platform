# ADR-0010: Sell single PDFs through Payhip now, a Stripe-native store later

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Free members and guests should be able to buy single PDFs from Stage 1. Products already exist on Payhip. Payhip's webhook is the only machine-readable record of which product was bought; its signature is a constant; it retries three times and has no sales API. Payhip charges 5% on its free plan. A store on Stripe Checkout has strong webhooks and no platform fee but needs products, prices, tax settings and pages built.

## Decision

Stage 1 integrates Payhip: Buy links carry a one-time reference, the webhook creates a purchase and an item entitlement, each sale is cross-checked against Stripe, and a CSV importer repairs gaps. Stage 2 adds Stripe prices per library item and moves items one by one; both channels can run side by side.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Payhip with webhook (chosen for Stage 1) | Low | 5% per sale | Fine | Good | Works with products that already exist; fastest to launch | Weak webhook authentication; no catch-up API |
| B. Stripe store from the start | Medium | Stripe fees only | Fine | Good | Strong events, bundles, coupons, one provider | Delays Stage 1; tax set-up needed first |
| C. Keep sending files by hand | None | Owner's time | Poor | – | Nothing to build | The problem Stage 1 exists to remove |

## Trade-off Analysis

A ships weeks earlier and its weaknesses are contained by the Stripe cross-check and the low value of each item. The purchase and entitlement path is shared, so B later reuses it.

## Consequences

- Easier: launch; guests buying without an account.
- Harder: two places to keep the catalogue in step until migration; the Store manager agent checks this from Stage 2.
- Revisit when: PDF sales pass roughly US$1,000 a month, where Payhip's fee exceeds the effort of moving.

## Action Items

1. [ ] Owner adds the webhook URL and redirect in Payhip (S1.6)
2. [ ] Add `stripe_price_id` to the manifest schema now, unused until Stage 2
