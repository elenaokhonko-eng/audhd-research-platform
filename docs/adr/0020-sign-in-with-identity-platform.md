# ADR-0020: Sign-in with Identity Platform: email link and Google, session held by the website

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

Members must prove control of the email that Substack and Stripe know, with as little friction as possible. There is no 'sign in with Substack'. v3 chose Identity Platform (free to 50,000 monthly users) with OpenID Connect as the exit path.

## Decision

Identity Platform with two methods: an emailed sign-in link and Google. Both yield a verified email. No passwords. `platform-api` verifies the sign-in token and issues the http-only session cookie, which the website stores and forwards; the website is the API's only caller and holds no rights to administer identities. The API verifies the session on each call. The owner is recognised from a configured list of account ids plus a second-factor sign-in. Entitlements attach only to verified emails.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Identity Platform (chosen) | Low | None at this size | Large | Good | Google-native, no fee, standard protocol | Sign-in emails need a properly authenticated sending domain |
| B. A hosted auth product | Low | Free tier, then per user | Large | Good | Polished screens and user management | Another vendor holding member identities |
| C. Passwords of our own | Medium | None | – | Poor | No dependency | Password storage and resets to secure; no benefit |

## Trade-off Analysis

A adds no vendor and no cost, and the verified-email property is exactly what entitlement matching needs.

## Consequences

- Easier: recognising Substack readers by email with no extra step.
- Harder: deliverability of sign-in emails; Google sign-in is the second route.
- Revisit when: organisations or team accounts are needed for licences.

## Action Items

1. [ ] Implement in S1.1
2. [ ] Set SPF, DKIM and DMARC for the sending domain in Terraform
