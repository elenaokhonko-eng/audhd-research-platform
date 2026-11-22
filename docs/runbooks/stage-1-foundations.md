# Stage 1 foundations runbook: folder, dev project and platform skeleton

Everything below runs in **Google Cloud Shell**, from the repository root, after Stage 0 ([stage-0.md](stage-0.md)) is done. One script does the work; a second one checks it. Both are safe to run again: every step checks before it creates.

Read the three warnings first.

> **1. The old preview site in the prod project is destroyed.** Applying `envs/prod` deletes the Cloud Run service `web-dev` in `audhd-neurobiology-prod`, its domain mapping and its Cloudflare record. From then on `web-dev` lives only in the dev project.
>
> **2. `dev.audhdneurobiology.org` is down for a while.** It is unavailable from the prod apply (step 4) until the dev apply (step 5) has created the new mapping, and then until Google has issued its new certificate (usually 15 to 60 minutes). The real site, `audhdneurobiology.org`, is not affected.
>
> **3. Production deploys need your approval from now on.** The prod deployer identity can only be used by a GitHub job in the environment `production`, on a tag starting with `v`. Once you are that environment's required reviewer, every production deploy waits for your click in GitHub.

## What the script creates

| Piece | Where |
| --- | --- |
| Folder `audhd-neurobiology` | Under the existing organisation. Holds both projects; access granted on it applies to both ([ADR 0014](../adr/0014-folder-now-own-organisation-later.md)) |
| Project `audhd-neurobiology-dev` | In the folder, on the same billing account as prod. Holds invented test data only |
| State bucket `gs://audhd-neurobiology-dev-tfstate` | Versioned, public access prevented. Terraform's record of the dev project |
| In **each** project (Terraform, `infra/terraform/envs/prod` and `envs/dev`) | Firestore database `(default)`; Pub/Sub topics `platform.events`, `inbound.webhooks` and their dead-letter topics; the push subscription `platform-events-to-api`; Cloud Run services `platform-api` (private) and `platform-hooks` (public); the Cloud Run job `platform-selfcheck`; one service account per component; an email alert when a message cannot be delivered |
| In the dev project only | The preview site `web-dev`, its own image registry and GitHub deploy identity, and (if your domains are mapped) `dev.audhdneurobiology.org` |
| Member pieces, in **each** project (`members.tf`) | The sign-in configuration (Identity Platform), the browser API key, the contact key (Cloud KMS), the private buckets `<project>-library`, `<project>-library-staging` and `<project>-roster-inbox`, and the DNS records of the sign-in email's sending domain (`audhdneurobiology.org` for prod, `auth.dev.audhdneurobiology.org` for dev). The sign-in runbook ([stage-1-sign-in.md](stage-1-sign-in.md)) finishes them; read its "Before you run anything" first |
| GitHub environments `dev` and `production` | Each holds `GCP_PROJECT_ID`, `GCP_REGION`, `WIF_PROVIDER`, `DEPLOYER_SA`, `RUNTIME_SA`, `REGISTRY` for its own project. Deploy workflows read them from there. `dev` accepts deploys only from the branch `integration/stage-1`; `production` only from tags starting with `v` |

Two terms used below. A **GitHub environment** is a named deploy target in the repository's settings, with its own variables and, optionally, people who must approve before a job may use it. A **service agent** is an identity Google itself runs inside a project for one product; Pub/Sub's agent is the one that moves undeliverable messages to the dead-letter topics.

**What it costs: nothing while idle.** Cloud Run services and the job scale to zero and are billed only while they answer a request or run; Pub/Sub and Firestore are billed per use, and an empty database and a few test messages stay inside the free tiers. Stored images cost a few cents a month at most; the registries delete images older than 30 days. The monthly budget alert set up in Stage 0 watches the prod project; the dev project is not part of it.

## Before you start

You need, in Cloud Shell:

- `gcloud` logged in as you, and `gh` logged in to GitHub (`gh auth status`; if not, `gh auth login`).
- Terraform in `~/bin` (installed by `00-bootstrap.sh`) and `infra/terraform/envs/prod/terraform.tfvars` from Stage 0.
- Your Cloudflare API token from Stage 0 (Zone:DNS:Edit on `audhdneurobiology.org`). Both applies need it, because `dev.audhdneurobiology.org` moves from one project to the other. If you no longer have it, create a new one: Cloudflare → My Profile → API Tokens → Create Token → template *Edit zone DNS*.
- On the organisation: the roles *Folder Creator* and *Project Creator* (which also lets you move a project into the new folder), and *Project Mover* to move the prod project out of its current parent (granted on the prod project itself is enough). An organisation administrator can grant them, for example:
  `gcloud organizations add-iam-policy-binding ORG_ID --member="user:YOUR_ACCOUNT" --role=roles/resourcemanager.folderCreator`

## Run it (about 20 minutes, plus certificate time)

```bash
cd ~/audhd-research-platform
git fetch origin && git checkout integration/stage-1 && git pull
bash ops/scripts/20-stage1-foundations.sh
```

The script sets `export TF_VAR_owner_member="user:$(gcloud config get-value account)"` for you, so Terraform can let your account add files to the upload buckets without your address being written into the repository. If you run `terraform plan` by hand later (the "No changes" check at the end), run that same line first in the same shell.

## What each prompt means

| Prompt | Answer |
| --- | --- |
| `Cloudflare API token:` | Paste the token and press Enter. Nothing is shown while you paste; it is kept in this shell session only and never written to a file. It is skipped if `TF_VAR_cloudflare_api_token` is already set. |
| `Move audhd-neurobiology-prod into the folder audhd-neurobiology now? [y/N]` | `y` moves the prod project into the folder. The project keeps its id, number, services and data; nothing restarts. Anything other than `y` skips the move and the script continues; re-run later to move it. |
| Terraform, first time: `Do you want to perform these actions?` (envs/prod) | Read the plan. Expect it to **destroy** `web-dev`, the mapping `dev.audhdneurobiology.org` and the `dev` CNAME record, and to **create** the platform resources and the member pieces listed above (sign-in configuration, API key, contact key, three buckets, the sending domain's DNS records). Expect one **update in place**: `web-prod` gets its sign-in settings as environment variables. An SPF or DMARC record you imported (sign-in runbook, "Before you run anything") also shows as an update in place. Nothing for `web-prod`, `audhdneurobiology.org` or `www` should be destroyed. Type `yes` to apply; anything else cancels, nothing changes, and the script stops: re-run it when you are ready. |
| Terraform, second time (envs/dev) | Expect **creates**, in the dev project: the resources listed above, including the member pieces (sign-in configuration, API key, contact key, three buckets, the DNS records of `auth.dev.audhdneurobiology.org`). If `web-dev` exists already from an earlier run, it shows as an **update in place** (its sign-in settings as environment variables) instead of a create. Nothing should be destroyed. Type `yes`. |

The script also asks Google to create Pub/Sub's service agent in each project before each apply (`gcloud beta services identity create --service=pubsub.googleapis.com`). Google normally creates that agent a little after the API is switched on, and Terraform's first apply would fail if it granted roles to an agent that does not exist yet.

Step 6 first builds the website (`apps/web`) and deploys it to `web-dev` in the dev project, with the dev website identity `web-runtime`, so the preview site shows the real site rather than Google's placeholder page. This does not depend on the platform service. Each re-run of the script deploys the commit you have checked out.

Step 6 then builds the first `platform-api` image and deploys it to both projects. If the service's code has not been merged yet (no `services/platform-api/Dockerfile`), the script says so and skips this part; `platform-api`, `platform-hooks` and `platform-selfcheck` keep Google's placeholder image. They get the real image once Core's service code and the platform-api image (S1.0 Task 6) have been merged: re-run the script then. After that, the workflow `.github/workflows/platform-api.yml` (S1.0 Task 6) deploys every new image: to dev on each push to `integration/stage-1` once `DEPLOY_DEV_ENABLED` is `true` on the environment `dev`, and to prod on a `v*` tag after your approval. It changes only the image of `platform-api`, `platform-hooks` and `platform-selfcheck`. The script's last message tells you which case you are in.

Step 7 also limits which code may deploy to each GitHub environment (a **deployment branch policy**): `dev` accepts jobs only from the branch `integration/stage-1`, `production` only from tags matching `v*`. It sends GitHub only that setting, never the list of reviewers, so a required reviewer you already set is kept; step 8 checks it afterwards. Re-running adds nothing when the rules exist. To see them:

```bash
gh api repos/elenaokhonko-eng/audhd-research-platform/environments/production/deployment-branch-policies --jq '.branch_policies[] | "\(.type) \(.name)"'
```

At the end it prints whether the `production` environment has a required reviewer. If it has none, make yourself the reviewer (GitHub → repository → Settings → Environments → production → Required reviewers), or run the command below. Its last two lines keep the tag rule of step 7 switched on:

```bash
gh api -X PUT repos/elenaokhonko-eng/audhd-research-platform/environments/production \
  -f 'reviewers[][type]=User' -F "reviewers[][id]=$(gh api user -q .id)" \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
```

## If it stops

| Message | What to do |
| --- | --- |
| `Error acquiring the state lock` | Another Terraform run holds the lock, or an earlier one was interrupted. Make sure no other run is active, then `(cd infra/terraform/envs/prod && terraform force-unlock LOCK_ID)` (or `envs/dev`), with the Lock ID from the error. Re-run the script. |
| An API `has not been used in project ... or it is disabled` | Wait one minute and re-run. |
| A Pub/Sub service account `service-...@gcp-sa-pubsub...` does not exist | Wait one minute and re-run; the agent is being created. |
| `The variable ... is missing` | The script names the file and the line to add. Add it and re-run. |
| Google refused to create the folder, the project, or the move | The message names the role your account lacks. |
| `gh is not logged in` | `gh auth login`, then re-run. |

## Check it: the smoke test

The smoke test needs the real `platform-api` image. It runs only after Core's service code and the platform-api image (S1.0 Task 6) have landed and step 6 of a re-run, or the platform-api CI deploy (`.github/workflows/platform-api.yml`), has deployed it. With the placeholder image, step a fails.

```bash
bash ops/scripts/smoke-platform.sh audhd-neurobiology-dev
```

It checks, in order, and stops at the first failure with `SMOKE FAILED at step <letter>`:

| Step | Checks |
| --- | --- |
| a | `platform-api /health`, called with your identity token, answers `"mode":"api"` |
| b | `platform-hooks /health`, called without a token, answers `"mode":"hooks"`; `/v1/ping` answers 404 there |
| c | The job `platform-selfcheck` runs and logs the id of the event it published |
| d | Within 60 seconds Firestore has the document `inbox/<event id>`: Pub/Sub delivered the event to `platform-api`, which accepted Pub/Sub's token and recorded it |
| e | The same event published again is logged by `platform-api` as a duplicate, and no handler runs |

Expected last line: `SMOKE PASSED (audhd-neurobiology-dev)`. Then both of these should say *No changes*:

```bash
terraform -chdir=infra/terraform/envs/prod plan
terraform -chdir=infra/terraform/envs/dev plan
```

## Gate 1: switch on dev deploys

Until you do this, pushes to `integration/stage-1` deploy nothing. When you are ready:

```bash
gh variable set DEPLOY_DEV_ENABLED --env dev --body true
```

From then on every push to `integration/stage-1` that changes `apps/web` deploys the website to `web-dev` in the dev project. To deploy it without a new commit, run the workflow by hand on that branch:

```bash
gh workflow run web.yml --ref integration/stage-1
```

A manual run on any other branch tests the site but deploys nothing. Only jobs in the GitHub environment `dev` can use the dev deploy identity.

To switch them off again: `gh variable delete DEPLOY_DEV_ENABLED --env dev`.

## Undo

Delete the dev project. Everything in it goes with it, including its state bucket; Google keeps the project recoverable for 30 days (`gcloud projects undelete audhd-neurobiology-dev`).

```bash
gcloud projects delete audhd-neurobiology-dev
gh api -X DELETE repos/elenaokhonko-eng/audhd-research-platform/environments/dev
```

This does not bring back `web-dev` in the prod project or `dev.audhdneurobiology.org`; that needs the Terraform change reverted in a pull request and `envs/prod` applied again. The platform resources in prod stay; the Firestore database there has delete protection on purpose. To take the prod project out of the folder again: `gcloud beta projects move audhd-neurobiology-prod --organization=ORG_ID`.
