# ADR-0025: Build Stage 1 with parallel lanes of Claude agents: contracts first, one session per lane, subagent-driven development inside each, the owner at fixed gates

**Status:** Proposed
**Date:** 2026-11-19
**Deciders:** Owner (Elena Okhonko)

## Context

Stage 1 has ten slices across five directories and a date-bound first release. One agent working through the slices in order would be too slow; many agents in one checkout would overwrite each other. Claude Code offers several ways to run agents in parallel (subagents, background sessions with worktrees, cloud sessions, projects with threads, experimental agent teams). Repository rules stay as they are: tests first, no personal data, module boundaries, and agents never apply infrastructure, deploy to production, push to `main` or merge their own pull request.

## Decision

The build is split into **lanes**, each with a set of paths it alone may change, its own branches and its own plan. Interfaces between lanes are written first, on one contracts page that only the integrator changes. Each lane is one Claude session (a cloud session, or a project thread where that feature is available) that executes its plan by subagent-driven development: a fresh implementer per task, a task review, a whole-branch review, then a pull request. Lanes run in waves; each wave ends at a gate that only the owner can pass (applying infrastructure, entering secrets, approving texts, merging). Reviews that cut across lanes (contracts, privacy, security, accessibility) are a lane of their own that writes no product code. Roles are defined once in `docs/swarm/` and mirrored as subagent definitions. The default is that the owner merges every pull request; an integration branch that the integrator may merge into, promoted to `main` by the owner once a day, is available and off until she switches it on.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Lanes with contracts first (chosen) | Medium | More model usage in parallel | Scales with independent directories | Good | Parallel work without file conflicts; every lane testable alone; gates match what only the owner may do | Needs discipline about the contracts page; the owner is the bottleneck at gates |
| B. One session, slice by slice | Low | Lowest | – | Good | Simple; least usage | Too slow for the first release date |
| C. Experimental agent teams in one session | Medium | High | Limited | Fair | Teammates talk to each other | No worktree isolation, teammates are lost on resume, interactive sessions only |
| D. Many agents on one branch | Low | High | Poor | Poor | No planning | Overwrites and broken builds |

## Trade-off Analysis

A spends tokens to buy calendar time and keeps each change small enough to review. It depends on S1.0 landing first, because the skeleton defines the conventions every lane follows.

## Consequences

- Easier: a blocked lane does not stop the others.
- Harder: a contract change costs a round trip through the integrator.
- The owner's time concentrates at four gates and at merges.
- Revisit when: the first wave is done; adjust the number of lanes to the usage the plan allows.

## Action Items

1. [ ] Owner approves the swarm plan and chooses how sessions are started and how merges happen
2. [ ] Integrator writes the lane plans for wave 1 and has them reviewed
3. [ ] Protect the `production` environment and `main` before the first lane starts
