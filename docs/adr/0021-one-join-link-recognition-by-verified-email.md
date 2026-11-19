# ADR-0021: One join link per audience; recognition by verified email, never by the link

**Status:** Proposed
**Date:** 2026-11-19
**Deciders:** Owner (Elena Okhonko)

## Context

The owner wants paid Substack subscribers to arrive on the platform by following a link, with nothing to pay and no code to paste, and free subscribers to arrive as free members with a route to paid. Substack has no webhook and no general API, so the platform cannot learn about a subscription from Substack directly. Links get forwarded and posted.

## Decision

An invitation is a **campaign**: a slug in the address (`/join/{slug}`), an audience and a time window. The slug selects wording and is recorded for counting. It grants nothing. Access comes only from verified facts: a sign-in that proves control of an email (email link or Google), matched to entitlements that came from Stripe, the roster or the owner. Grant policies of every open campaign apply to any member who meets them, whichever link they used. Invitations are delivered through Substack posts and Substack's welcome emails; the platform sends only the sign-in link a person asked for.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. One link per audience, recognition by verified email (chosen) | Low | None | Large | Good | A forwarded link is harmless; no bulk email; future subscribers are invited automatically by Substack's welcome email | A reader who uses another email at Substack is not recognised without help |
| B. A personal signed link emailed to each subscriber | Medium | Email service | Large | Fair | Recognises a person even when sign-in uses another address | Bulk email from a new domain; a link that carries rights can be forwarded; needs every address imported first |
| C. A shared invite code that unlocks paid access | Low | None | – | Poor | Simplest to build | Access on a secret that will leak; breaks 'never grant on a guess' |

## Trade-off Analysis

A keeps the entitlement rules intact and needs no personal data beyond what the paid-status sources already hold. Its weak spot, the reader with two addresses, is met by a plain message, a support request and a manual grant that takes seconds.

## Consequences

- Easier: one link in a post or a welcome email works for everyone, for good.
- Harder: nothing can be promised to someone who has not signed in.
- `invite_waves` becomes `campaigns`; the slug is the id.
- Revisit when: the platform sends its own member email and personal links would help re-engagement.

## Action Items

1. [ ] Implement in the launch track (entitlements and web lanes)
2. [ ] Owner places the links in a paid-only post, a free post and Substack's welcome emails
