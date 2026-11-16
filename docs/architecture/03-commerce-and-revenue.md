# 03 · Commerce and revenue (M14)

**Status:** Proposed for review · 2026-11-16 · Stage 1 (Stripe sync, Payhip purchases, revenue mart) and Stage 2 (Stripe store, Revenue team, owner cockpit)

This module turns money events into two things: facts the membership module can act on, and one honest picture of revenue across every channel.

## 1. Three channels, one Stripe account

| Channel | What is sold | Who runs checkout | How the platform learns of a sale | Platform fee |
| --- | --- | --- | --- | --- |
| **Substack** | Monthly and annual newsletter subscriptions, which include full platform access | Substack, charging through the owner's Stripe account | Stripe webhook; Substack's subscriptions are ordinary subscription objects in the owner's account, marked with Substack's application id | Substack takes 10% of each payment, plus Stripe's fees |
| **Payhip** | Single PDFs for free members and guests (Stage 1) | Payhip, charging through the same Stripe account (and PayPal if enabled) | Payhip webhook: it is the only machine-readable record of *which* product was bought | 5% on the free plan, plus Stripe's fees; Payhip may also withhold sales tax for some countries inside its fee |
| **Platform** | Platform-only membership (Stage 1); single PDFs and bundles through a Stripe-native store (Stage 2) | Stripe Checkout, created by the platform | Stripe webhook | Stripe's fees only |

Checked against the live account on 2026-11-16: the account's event log contains `customer.subscription.created`, `customer.subscription.updated`, `invoice.paid` and `invoice.payment_failed` events for subscriptions created by Substack, and no webhook endpoint is registered yet. Registering one endpoint is all that is needed to receive them. See [ADR 0007](../adr/0007-stripe-is-the-source-of-truth-for-paid-status.md).

Channel is decided by one field on each Stripe object: `application` equals Substack's id, Payhip's id, or nothing (the platform's own sale). The ids are configuration, kept outside this repository.

## 2. Rules for touching Stripe

1. **Read-only towards anything Substack or Payhip created.** The platform never updates, cancels or refunds those objects. Refunds for Substack are done in Substack; refunds for Payhip in Payhip.
2. **Restricted keys, one per consumer.** The sync job gets a key that can only read customers, subscriptions, invoices, charges and balance transactions. The checkout creator gets a key that can only create Checkout Sessions and read prices. No service holds the full secret key.
3. **Never press "Disconnect Stripe" in Substack.** That button cancels and refunds every paid subscriber. Leaving Substack is done through Substack support (§8).
4. **Test in a sandbox.** Development uses a Stripe sandbox with test clocks to play a year of renewals and failures in minutes. The live account is touched only by the read-only backfill and the production webhook.

## 3. Stage 1: importing and listening

### 3.1 Backfill (once, then nightly as reconciliation)

```mermaid
flowchart LR
  A[stripe-reconcile job] --> B[List all customers]
  A --> C[List all subscriptions,<br/>every status]
  A --> D[List charges and<br/>balance transactions]
  B --> E[Upsert contacts<br/>with channel flags]
  C --> F{application?}
  F -->|Substack| G[commerce.subscription.changed<br/>channel=substack]
  F -->|none| H[commerce.subscription.changed<br/>channel=platform]
  D --> I[revenue_events in BigQuery<br/>classified by channel]
  G --> J[M2 grants or ends<br/>tier:paid entitlements]
  H --> J
```

- **Every Stripe customer becomes a contact**, with the flag of each channel they came through: paid subscriber, past subscriber, Payhip buyer, guest. Only customers with a live subscription or a grant receive `tier:paid`.
- The first production run is a **dry run that writes a report and nothing else**: how many contacts, how many paid by channel, and the list of anything odd (two customers with one email, a subscription with no email). The owner compares the paid count with the Substack dashboard before the real run.
- The nightly run repeats the comparison. Stripe retries a failed webhook for three days and does not guarantee order, so reconciliation is what makes the result certain rather than likely.

### 3.2 Webhooks

```mermaid
sequenceDiagram
  autonumber
  participant S as Stripe
  participant H as platform-hooks (public)
  participant P as Pub/Sub
  participant C as M14 consumer (platform-api)
  participant M as M2 membership
  participant B as BigQuery
  S->>H: Event (signed)
  H->>H: Verify Stripe signature, reject if older than 5 minutes
  H->>P: Publish raw event to inbound.webhooks
  H-->>S: 200 within a second
  P->>C: Push
  C->>C: Create inbound_events record if absent, else stop
  C->>C: Classify channel by application id
  C->>M: commerce.subscription.changed or commerce.purchase.recorded
  M->>M: Grant, renew or end entitlement
  C->>B: revenue_events row
```

| Stripe event | Effect |
| --- | --- |
| `customer.subscription.created`, `.updated` | Grant or refresh the entitlement to the new period end; mark `grace` on `past_due`; note "ends on" when cancellation at period end is set |
| `customer.subscription.deleted` | End the entitlement |
| `invoice.paid` | Revenue row; renewal confirmed |
| `invoice.payment_failed` | Revenue note; entitlement to `grace` |
| `charge.refunded`, `charge.dispute.created` | Revenue row; revoke the matching entitlement or purchase |
| `checkout.session.completed` | Platform sale: create the purchase or the platform subscription |
| `customer.updated` (email changed) | Move the channel flag to the new contact; keep the old one linked |

The endpoint pins its Stripe API version, so a Stripe upgrade cannot change payload shapes unannounced.

## 4. Stage 1: single PDFs through Payhip

```mermaid
sequenceDiagram
  autonumber
  participant U as Free member
  participant W as web
  participant A as platform-api
  participant Y as Payhip
  participant H as platform-hooks
  U->>W: Clicks Buy on a library item
  W->>A: Create checkout reference for (member, sku)
  A-->>W: Payhip link with metadata[ref]=one-time reference
  W-->>U: Redirect to Payhip checkout
  U->>Y: Pays
  Y->>H: Webhook "paid": items[].product_key, email, metadata.ref
  H->>A: via Pub/Sub
  A->>A: Map product_key to sku, resolve ref to member (or email to contact)
  A->>A: Record purchase, grant item:<sku>
  Y-->>U: Redirect back to /member/library?purchased=sku
  U->>W: Opens My purchases, downloads
```

What the design has to respect, because Payhip is simple:

| Payhip fact | Design answer |
| --- | --- |
| The checkout cannot be pre-filled with the buyer's email, and buyers mistype or use another address | The Buy link carries a one-time reference (`metadata[ref]`) that Payhip returns in the webhook; the platform resolves it to the signed-in member. Guests buying on Payhip directly are matched by email and attach when they register. |
| The webhook "signature" is a constant derived from the API key, not a signature of the message | Treat the webhook as weakly authenticated: an unguessable endpoint path, constant-time comparison of the signature, one record per transaction id, and a **cross-check in Stripe** (a payment by Payhip's application, same amount, same minute) before the purchase is marked verified. PayPal-paid orders cannot be cross-checked and are flagged for a glance. |
| Three hourly retries, then the event is gone; there is no API to list sales | A weekly reminder to upload Payhip's sales CSV in the admin screen; the importer fills any gap. Payments by Payhip's application seen in Stripe without a matching purchase raise an alert the same day. |
| Payhip emails the PDF itself | Fine: the buyer has the file at once, and the workspace copy is the permanent, always-current one. |
| Refund event carries the amount | A full refund revokes the item; a partial refund is flagged for the owner. |

Each library item maps to a Payhip product by `product_key` in its manifest ([04](04-content-library-and-search.md)). A sale of an unmapped product is recorded and flagged, never dropped.

## 5. Stage 1: platform-only membership

A Stripe product "Platform membership" with a monthly and an annual price, bought through Stripe Checkout from the upgrade page. The session carries the member id as `client_reference_id`; the webhook creates a `platform_stripe` entitlement with scope `platform_only`. Cancelling and card changes go through Stripe's hosted customer portal, so the platform builds no billing screens. Stripe Tax is switched on at this point, because this is the first sale the owner makes without a marketplace in between; GST registration thresholds are a question for an accountant.

The upgrade page always shows both routes side by side: **Subscribe on Substack** (newsletter and platform) and **Platform only**.

## 6. Stage 2: the Stripe-native store

Payhip is the quick start; the store replaces it item by item without a migration day.

- Each library item gains a Stripe price; **Buy** opens Stripe Checkout; the purchase and entitlement path is the one already built for platform membership.
- Bundles and series passes become one more grant type (`bundle:<id>` expands to items).
- Coupons, pay-what-you-want and gift purchases come from Stripe features, not custom code.
- Payhip keeps running for items that have not moved. An item moves by adding `stripe_price_id` to its manifest.
- Decision and trade-offs: [ADR 0010](../adr/0010-payhip-now-stripe-store-later.md).

## 7. One revenue picture

Everything lands in BigQuery `ops_commerce` ([09 §3](09-events-and-data-model.md)), keyed by contact id, no emails.

| Question the owner asks | Answered from |
| --- | --- |
| Total revenue this month, gross and net of every fee, by channel | `revenue_events`. Substack's and Payhip's cuts are on each sale's balance transaction. Stripe's own fees (card, currency conversion, billing) are posted as **daily totals by kind**, not per sale: they are stored as their own rows and shared out across channels in proportion to that day's volume, and the view says so. |
| Who buys what: free members, paid members, guests | `revenue_events` joined to `membership_daily` |
| Plan mix: monthly, annual, founding, platform-only | `membership_daily` |
| Upgrades, downgrades, cancellations, and why | `tier_changes` |
| Which PDFs sell, and to which segment | `revenue_events` by `sku` |
| Money from readers billed by Apple | A separate manual line: Apple pays Substack in monthly lumps, not per reader, so it never appears per person in Stripe |

### The owner cockpit: decisions, not charts

The cockpit in `/admin` does not copy Substack's dashboard. Each card is a **decision**: a signal, a proposed action, the expected effect, and a switch.

| Card | Signal | Action when switched on | Executed through |
| --- | --- | --- | --- |
| Invite to upgrade | Free members with high engagement or two or more purchases | Upgrade invitation with both routes | Email port; Substack post |
| Win back | Paid readers who cancelled in the last 60 days | Offer, or a one-month complimentary pass | Substack offer (manual link until the Desk capability is verified) |
| Annual push | Monthly payers for six months or more | Annual-plan offer | Substack offer |
| Paywall timing | A free article still drawing sign-ups after N days | Move it behind the paywall, or keep it free | Substack Desk post audience |
| Open one up | A paid article with unusually high engagement | Free for a week, announced with a Note | Substack Desk |
| Bundle | PDFs often bought together | Create the bundle price | Stripe |
| Price test | Conversion by price point | Change a price for new buyers | Stripe, Payhip |
| Renewal risk | Annual renewals due in 30 days with low recent activity | Personal note from the owner | Email draft for approval |

Nothing switches itself on. Every executed action is recorded with its result two and four weeks later, so the next proposal is better informed.

### Revenue team (Stage 2)

Three agents on the model gateway, reading only Zone 1b:

| Agent | Does | Hands to |
| --- | --- | --- |
| **Revenue analyst** | Weekly: what changed, what it means, what is unusual. Raises `revenue.insight.raised`. | Cockpit, Revenue manager |
| **Revenue manager** | Turns insights into cockpit cards with an expected effect and a way to measure it (`promo.proposed`) | The owner; on approval, the Marketing team |
| **Store manager** | Keeps the product catalogue consistent across the library manifest, Payhip and Stripe; checks every sale has an entitlement and every refund a revocation; drafts product pages | The owner |

The Revenue manager and the Marketing team share one calendar: a promotion approved here becomes a brief there (`promo.approved`), and the marketing results flow back as revenue events.

## 8. Exit paths

- **Leaving Payhip:** stop linking to it; purchases and entitlements are already in the platform.
- **Leaving Substack:** the subscriptions and cards live in the owner's Stripe account and keep running. Ask Substack support to disconnect without cancelling and to release the 10% fee; do not use the Disconnect button. Entitlements then change source from `substack_stripe` to `platform_stripe`; nothing else in the platform changes. Readers billed by Apple cannot be moved and would need to re-subscribe.
- **Leaving Stripe:** the `PaymentProvider` port has three calls (create checkout, parse event, list subscriptions). Paddle or Lemon Squeezy fit the same shape.
