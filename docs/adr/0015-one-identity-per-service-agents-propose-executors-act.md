# ADR-0015: One identity per service and agent team; agents propose, executors act

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

The owner asked whether each agent group needs a credentials key file. Agents read untrusted text (comments, web pages) and could be manipulated. Publishing, posting, sending and price changes must have a human approval that cannot be bypassed.

## Decision

No key files. Every service, job and agent team runs as its own service account with the least permissions it needs, all declared in one `identities.tf` per environment. Agent identities can read their inputs and write proposals only. Separate executor identities hold the permission to publish, post or change prices, and act only on proposals marked approved.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. One shared service account | Lowest | None | – | Poor | Nothing to manage | Any fault or manipulated agent can do everything |
| B. One identity each, with the agent and executor split (chosen) | Medium | None | – | Good | Least privilege; the approval gate is enforced by permissions, not by prompts | More accounts and bindings to declare |
| C. A key file per agent group | Medium | None | – | Poor | Familiar from other platforms | Long-lived secrets to store, rotate and leak |

## Trade-off Analysis

B costs some Terraform and removes both stored credentials and the possibility of an agent acting on its own.

## Consequences

- Easier: reviewing who can do what by reading one file.
- Harder: each new job or team needs its identity declared first.
- Revisit when: the number of teams makes per-team accounts unwieldy; group by trust level then.

## Action Items

1. [ ] Create `identities.tf` in S1.0
2. [ ] Add executors with the approval kit in Stage 2
