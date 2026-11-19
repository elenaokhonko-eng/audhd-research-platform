# Stage 0 runbook: audhdneurobiology.org on Cloud Run

Everything below runs in **Google Cloud Shell** (console.cloud.google.com, the `>_` icon top right). Cloud Shell already has `gcloud`, `docker`, `git` and `gh`, and is already logged in as you. The bootstrap script installs Terraform into `~/bin` the first time. Nothing to install on Windows.

Three steps need a browser, and each is marked **browser**. Everything else is a command.

## What you get

| Piece | Where |
| --- | --- |
| Website, production | `web-prod` on Cloud Run → https://audhdneurobiology.org and https://www.audhdneurobiology.org |
| Website, preview for testing | `web-dev` on Cloud Run → https://dev.audhdneurobiology.org (not indexed by search engines). Since Stage 1 it runs in the dev project: [stage-1-foundations.md](stage-1-foundations.md) |
| Images | Artifact Registry `asia-southeast1-docker.pkg.dev/<project>/platform/web:<commit>` |
| Deploys | Superseded by [stage-1-foundations.md](stage-1-foundations.md): pushes to `integration/stage-1` deploy dev once `DEPLOY_DEV_ENABLED` is set (Gate 1). Push a tag `v0.1.0` → prod, after you approve in GitHub |
| Health | `/api/healthz`, checked every 5 minutes; email alert if it fails for 5 minutes |
| Budget | Monthly budget, emails at 50 %, 90 %, 100 % |
| Code for all of it | `infra/terraform/`, `.github/workflows/`, `ops/scripts/` |

## 0a. Get the branch onto GitHub (only if it is not there yet)

If you received `stage-0-foundation.bundle` instead of a pushed branch: in Cloud Shell click the three-dot menu > Upload, choose the bundle, then:

```bash
gh auth login                                   # (browser) GitHub.com, HTTPS, web browser
gh repo clone elenaokhonko-eng/audhd-research-platform && cd audhd-research-platform
git fetch ~/stage-0-foundation.bundle stage-0-foundation:stage-0-foundation
git push -u origin stage-0-foundation
gh pr create --base main --head stage-0-foundation --fill
```

Then skip to step 1 (you are already inside the repo on that branch after `git checkout stage-0-foundation`).

## 0. Once: GitHub login inside Cloud Shell

```bash
gh auth login            # choose GitHub.com, HTTPS, login with a web browser  (browser)
gh repo clone elenaokhonko-eng/audhd-research-platform
cd audhd-research-platform
git checkout stage-0-foundation   # or main, once merged
```

## 1. Bootstrap (about 10 minutes)

```bash
ALERT_EMAIL=elena.okhonko@gmail.com bash ops/scripts/00-bootstrap.sh
```

If you have more than one billing account the script stops and lists them; re-run with `BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX` in front. Terraform shows its plan and asks `yes` once.

If the first apply fails on the budget with "API not enabled", wait one minute and run the script again; it skips what exists.

At the end it prints two `run.app` URLs. Open the dev one: that is your site, already on Google Cloud.

## 2. Domain (15 to 60 minutes, mostly waiting)

1. **browser** Verify ownership once: `gcloud domains verify audhdneurobiology.org`, open the link, choose *Domain*, provider *Cloudflare*, follow it to the end.
2. **browser** Cloudflare token: Cloudflare → My Profile → API Tokens → Create Token → template *Edit zone DNS* → zone `audhdneurobiology.org` → Create. Copy it.
3. Run:

```bash
export TF_VAR_cloudflare_api_token='paste-token-here'
bash ops/scripts/10-domain.sh
```

The script finds the zone, creates the three Cloud Run domain mappings and the Cloudflare records (DNS only, grey cloud), and prints the certificate status. When `curl -sI https://audhdneurobiology.org/api/healthz` returns `200`, run the last two lines the script prints to move the uptime check onto the real domain.

## 3. Protect production (2 minutes)

```bash
gh api -X PUT repos/elenaokhonko-eng/audhd-research-platform/environments/production \
  -f 'reviewers[][type]=User' -F "reviewers[][id]=$(gh api user -q .id)"
gh api -X PUT repos/elenaokhonko-eng/audhd-research-platform/environments/dev
```

From now on a prod deploy waits for your click in GitHub.

## Day to day

| I want to | Do |
| --- | --- |
| Change the site and preview it | Since Stage 1: merge into `integration/stage-1` once dev deploys are switched on ([stage-1-foundations.md](stage-1-foundations.md)). Two minutes later it is on dev.audhdneurobiology.org |
| Publish to the real site | `git tag v0.1.1 && git push origin v0.1.1`, then approve the run in GitHub → Actions |
| Roll back prod | `gcloud run services update-traffic web-prod --region asia-southeast1 --to-revisions=PREVIOUS_REVISION=100` (list with `gcloud run revisions list --service web-prod --region asia-southeast1`) |
| See logs | `gcloud run services logs read web-prod --region asia-southeast1 --limit 50` |
| Check drift | `cd infra/terraform/envs/prod && terraform plan` should say *No changes* |

## Site is down

1. `curl -s https://audhdneurobiology.org/api/healthz` and the run.app URL from `terraform output web_prod_url`. If run.app works and the domain does not, it is DNS or the certificate: `gcloud beta run domain-mappings describe --domain audhdneurobiology.org --region asia-southeast1`.
2. If both fail: `gcloud run services logs read web-prod --region asia-southeast1 --limit 100`, then roll back (table above).

## Exit criteria for Stage 0

- [ ] `https://audhdneurobiology.org` serves the current design from Cloud Run
- [ ] `terraform plan` shows no changes
- [ ] a push to `main` deploys to dev without anyone touching the console
- [ ] the uptime check is green and points at the real domain
- [ ] the budget exists (`gcloud billing budgets list --billing-account=...`)
- [ ] Vercel project paused
