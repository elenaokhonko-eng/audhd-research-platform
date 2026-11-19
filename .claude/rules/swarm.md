# Lanes of the Stage 1 build

If your first message names you a lane of the Stage 1 build (L0 to L8), read `docs/swarm/README.md` and `docs/swarm/roles.md` before anything else, and change only the paths your lane owns (`docs/plans/stage-1-swarm-build-plan.md`, section 2).

- Interfaces between lanes are on `docs/contracts/stage-1-launch.md`. Build exactly what it says. To change it, open a pull request labelled `contract-change`; do not build ahead of it.
- One implementer at a time in one checkout. Every task gets a review by an agent that did not write it.
- Commit and push after every task. Open pull requests as drafts through `gh api`, never with a force-push.
- A merge is the owner's act. So are `terraform apply`, production deploys, secrets and anything on the live Stripe account.

If you were not started as a lane, this file asks nothing of you beyond `CLAUDE.md`.
