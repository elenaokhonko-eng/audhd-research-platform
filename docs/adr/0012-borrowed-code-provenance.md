# ADR-0012: Borrow only what the licence allows, and record where it came from

**Status:** Proposed
**Date:** 2026-11-16
**Deciders:** Owner (Elena Okhonko)

## Context

The platform reuses code from many reviewed repositories with different licences, and some with none. This repository is public, so anything copied into it is distributed at once. Three packages are meant to be extractable and released on their own later.

## Decision

Code is ported only from sources whose licence permits it (MIT, Apache-2.0, BSD and similar), keeping their notices. Unlicensed, non-commercial and copyleft sources contribute ideas only. Every ported file or skill is recorded in `THIRD_PARTY.md` in the pull request that adds it: source, commit, path, licence, target, changes. In the extractable packages, a file whose origin needs a second look before release carries a `PROVENANCE` first line.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Copy without tracking | None | None now | – | – | Fastest | A release later means auditing every file from memory |
| B. Permissive sources only, recorded at copy time (chosen) | Low | Minutes per pull request | – | Good | Nothing to untangle later; notices are kept | A small standing chore; a few sources are read for ideas only |
| C. Any source, sorted out at release | Low | None now | – | Poor | Widest choice of code | The repository is public, so copying is already distribution |

## Trade-off Analysis

Nothing essential in the borrow map exists only under a restrictive licence, so B costs almost nothing compared with C and removes the question entirely.

## Consequences

- Easier: open-sourcing a package; answering a licence question.
- Harder: nothing material.
- Revisit when: a needed component exists only under a restrictive licence.

## Action Items

1. [ ] Keep `THIRD_PARTY.md` current
2. [ ] Keep the rule in `CLAUDE.md`
