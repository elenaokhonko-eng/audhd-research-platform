# Swarm operating manual

**Status:** In force · approved by merge on 2026-11-19 · settings chosen by the owner on 2026-11-20 · **Plan:** [Stage 1 swarm build plan](../plans/stage-1-swarm-build-plan.md) · **Decision:** [ADR 0025](../adr/0025-build-with-lanes-contracts-first.md)

How the lanes of the Stage 1 build work day to day. `CLAUDE.md` at the repository root always wins over this page.

## Settings the owner controls

| Setting | Value | Meaning |
| --- | --- | --- |
| `merge_mode` | `integration-branch` | `owner`: the owner merges every pull request. `integration-branch`: lanes target `integration/stage-1`; a pull request into it is merged by an agent that did not write it (the integrator merges the lanes' pull requests, the quality lane merges the integrator's) after CI and its reviews pass; the owner promotes the branch to `main` once a day from one digest. Change this line to switch. |
| `max_parallel_lanes` | `3` | How many lanes run at once |
| `lane_plan_approval` | `integrator` | `integrator`: step-by-step lane plans are reviewed by an independent plan reviewer and the integrator; the owner can read them and is not waited for. `owner`: each lane plan waits for her |

## What every lane session does first

1. Read `CLAUDE.md`, this page, [roles.md](roles.md), the [contracts](../contracts/stage-1-launch.md) and its own lane plan in `docs/superpowers/plans/`.
2. Confirm which paths it owns ([plan §2](../plans/stage-1-swarm-build-plan.md)). If the first task needs a path it does not own, stop and say so.
3. Create its branch from the current target (`integration/stage-1` while `merge_mode` is `integration-branch`, otherwise `main`) as `<prefix>/<short-task-name>`, and open its pull requests against that target.
4. Run its plan with the `superpowers:subagent-driven-development` skill. If that skill is not available in the session, follow [roles.md](roles.md), which states the same loop in plain words.

## The loop for one task

1. The controller records the current commit, writes the task brief to a file and dispatches one **implementer** with the brief's path. Never two implementers at once in one checkout.
2. The implementer writes the failing test, runs it and sees it fail, implements, runs the lane's checks, commits, and writes its report to a file.
3. The controller writes the diff since the recorded commit to a file and dispatches one **task reviewer** with the brief, the report and the diff.
4. If the reviewer finds a gap, the same implementer fixes it and the reviewer checks the fix. After three rounds the controller decides, writes the decision in the ledger, and moves on or stops.
5. The controller appends one line to the ledger: the task, the commits, the review result.

The ledger lives in `.superpowers/sdd/` (ignored by git) and is the lane's memory. After any interruption, the ledger and `git log` say where to resume.

## A pull request is ready when

- Its tests were written first and pass; `ruff`, `mypy`, `lint-imports` (Python) or the type check and build (web) pass; `terraform fmt -check` passes for infrastructure.
- `bash ops/scripts/check-private-content.sh` passes. No real email, name, provider id, price, date of a promotion or subscriber number appears anywhere in the diff, the tests or the commit messages.
- It changes only paths its lane owns, or carries the `cross-lane` label.
- It adds or changes nothing that the contracts page does not already describe.
- The architecture page for the changed behaviour is updated in the same pull request; an ADR is added if a decision changed.
- A fresh branch reviewer has read the whole branch.
- Its description has four parts: **What changed** · **How it was tested** (commands and the summary lines) · **Reviews** (task reviews, branch review, any open finding with the reason it stays open) · **What the owner must do** (commands for Cloud Shell, or "nothing").

Pull requests are opened with `gh api repos/<owner>/<repo>/pulls -X POST --input <file>`, as drafts until the branch review is done. Labels: `lane:<name>`, `wave:<n>`, and where they apply `cross-lane`, `contract-change`, `needs-owner`, `blocked`.

## Changing a contract

1. The lane that needs the change opens a pull request against `docs/contracts/` with the label `contract-change`, stating who is affected.
2. The integrator decides, raises the version at the top of the page, and tells the affected lanes.
3. Code that depends on the change is merged after it, never before.

## What no lane does

Run `terraform apply`. Deploy to production. Push to `main`. Merge its own pull request. Force-push. Write to the live Stripe account. Call Substack's private endpoints. Ask for a secret in chat or write one to a file. Use real people's data in a test. Extend the legacy prototype folders. Start another lane.

## Kick-off prompts

Replace the parts in angle brackets. One prompt starts one lane.

### Integrator (start this one first)

```text
You are the integrator (lane L0) of the Stage 1 build of audhdneurobiology.org.
Read CLAUDE.md, docs/swarm/README.md, docs/swarm/roles.md, docs/plans/stage-1-swarm-build-plan.md,
docs/superpowers/specs/2026-11-19-launch-invites-grants-promotions-design.md and docs/contracts/stage-1-launch.md.

Your first job, Wave 0: for each lane that runs in Wave 1 (L1 Core, L3 Infra, L2 Web, L6 Desk), turn its
task cards into a step-by-step plan with the superpowers:writing-plans skill, one file per lane under
docs/superpowers/plans/, each naming the design and the contracts page as its spec. The existing S1.0 plan
already covers Core task C1 and Infra task I1: reuse it, add only what the swarm plan adds.
Have one fresh subagent review each plan against the design and the contracts before you commit it.
Open one pull request with the plans. Then stop and report which lanes can start.

You change only the paths lane L0 owns. You never start another lane's work yourself.
```

### Any other lane

```text
You are the controller of lane <L1 Core> of the Stage 1 build of audhdneurobiology.org.
Read CLAUDE.md, docs/swarm/README.md, docs/swarm/roles.md (the controller section),
docs/contracts/stage-1-launch.md and your plan: docs/superpowers/plans/<file>.

Work only in the paths your lane owns (docs/plans/stage-1-swarm-build-plan.md, section 2).
Execute your plan task by task with the superpowers:subagent-driven-development skill.
Open one draft pull request per task card, following "A pull request is ready when" in docs/swarm/README.md.
Commit and push after every task so the work survives an interruption.
Stop and label the pull request needs-owner in the cases listed in the swarm plan, section 9.
When your plan is finished, or you are waiting at a gate, post a hand-over summary and stop.
```

### Quality lane

```text
You are lane L7 Quality of the Stage 1 build of audhdneurobiology.org. You write no product code.
Read CLAUDE.md, docs/swarm/README.md, docs/swarm/roles.md (contract checker, privacy checker, security
reviewer, accessibility reviewer) and docs/contracts/stage-1-launch.md.

For each open pull request labelled lane:* that has no review from you: read its diff, run the contract
check and the privacy check, and post your findings as one review comment, most serious first, each with
file, line, what is wrong and what would make it right. For pull requests that touch sign-in, sessions,
admin routes, signed links, permissions or CI, add the security review. For apps/web, add the
accessibility review. Do not push to another lane's branch. Report what you reviewed and stop.
```

### Project instructions (only if the build runs as a Claude Code project)

```text
This project builds Stage 1 of audhdneurobiology.org in the audhd-research-platform repository.
Every thread is one lane or one task of a lane. Before any work a thread reads CLAUDE.md,
docs/swarm/README.md, docs/swarm/roles.md and docs/contracts/stage-1-launch.md, and changes only the paths
its lane owns (docs/plans/stage-1-swarm-build-plan.md, section 2).
- Branch from main; open one draft pull request per task card; never merge, never force-push, never push to main.
- Before calling work done: run the checks listed under "A pull request is ready when" and paste their summary lines.
- If something needed is missing (a secret, an account id, access, a decision), say exactly what and stop. Do not substitute, mock or guess.
- Never run terraform apply, never deploy to production, never write to the live Stripe account.
- Run at most three threads at a time. Propose threads and wait for my go-ahead before starting them.
```
