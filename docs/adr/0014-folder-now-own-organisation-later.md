# ADR-0014: A folder and a separate dev project now; an own organisation later

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

The production project sits in an existing Google Cloud organisation and billing account that also serve other work. ADR 0002 required a separate dev project before personal data is stored. Google Cloud organisations cannot be nested. Projects can be moved between organisations without changing ids or stopping services, and a billing account can pay for projects in any organisation.

## Decision

Create a folder for the platform under the existing organisation, with access granted at the folder. Create `audhd-neurobiology-dev` in it and move the prod project into it. Dev holds invented data only. Create an organisation on the platform's own domain and move both projects there before the first external data-use agreement. Before personal data is imported, settle which legal entity operates the platform and confirm that the billing arrangement is permitted for it.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Leave one project in the company organisation | None | None | – | – | No work | Real and test data together; unclear separation from other work |
| B. Folder and dev project now, own organisation later (chosen) | Low | None | – | Good | Separation today; billing unchanged; the move is planned | Administrators of the existing organisation can still reach the folder |
| C. Own organisation now | Medium | May change billing | – | Good | Clean from the start | A domain identity account to set up and a migration during Stage 1 |

## Trade-off Analysis

B gets the isolation that matters now without spending Stage 1 on a migration, and names the deadline for C.

## Consequences

- Easier: testing with invented people; a clear place for platform-wide policies.
- Harder: two Terraform roots and two sets of CI variables.
- Revisit when: billing changes, a legal entity for the platform exists, or a data-use agreement is in sight.

## Action Items

1. [ ] S1.0 foundations script creates the folder and the dev project
2. [ ] Owner settles the operating-entity and billing questions
