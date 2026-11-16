# ADR-0012: Record the origin of every borrowed file

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

The platform reuses code from many reviewed repositories. The owner has decided to copy what is useful now and to sort out licences only if a part is open-sourced later. This repository, however, is public today, so anything copied into it is already being distributed. Three packages are meant to be extractable.

## Decision

Every ported file or skill is recorded in `THIRD_PARTY.md` in the pull request that adds it: source, commit, path, licence, target, changes. Source licence headers are kept. In the extractable packages, a file derived from an unlicensed, non-commercial or copyleft source carries a `PROVENANCE` first line. In practice the borrow map takes code only from permissively licensed sources and takes ideas only from unlicensed ones, because the repository is public.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Copy without tracking | None | None now | – | – | Fastest | A release later means auditing every file from memory |
| B. Track provenance at copy time (chosen) | Low | Minutes per pull request | – | Good | Triage later is a search; notices are kept | A small standing chore |
| C. Permissive sources only, enforced | Low | None | – | Good | No triage ever | Stricter than the owner asked for |

## Trade-off Analysis

B keeps the owner's freedom to copy and makes the later decision cheap. It differs from C only on paper today, since nothing essential comes from a restricted source.

## Consequences

- Easier: open-sourcing a package; answering a licence question.
- Harder: nothing material.
- Revisit when: a needed component exists only under a restrictive licence.

## Action Items

1. [ ] Create `THIRD_PARTY.md` now
2. [ ] Add the rule to `CLAUDE.md`
