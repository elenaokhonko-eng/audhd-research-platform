# Operations runbook: day-to-day commands

The commands you use after launch, one example each. They run in **Google Cloud Shell**, from the repository root (`~/audhd-research-platform`). The launch itself is in [launch.md](launch.md).

Every example below uses placeholders: `<your project>` is `audhd-neurobiology-prod` (or `audhd-neurobiology-dev` to try a command first), `you@example.org` stands for a real address, and `<...>` is a value you fill in. Never put a real address, id or key into a file of the repository.

Every read and change through `platform-cli` is written to the audit log under your account. Its output never shows an address: anything shaped like one is printed as `[email]`.

## Before any command

Once per Cloud Shell session: choose the project, make `platform-cli` available, and point it at that project's `platform-api`.

```bash
cd ~/audhd-research-platform
PROJECT="<your project>"
ENV="${PROJECT##*-}"            # prod or dev: the Terraform root of that project
command -v uv >/dev/null || python3 -m pip install --user --quiet uv
alias platform-cli='uv run --project "$HOME/audhd-research-platform/services/platform-api" platform-cli'
terraform -chdir="infra/terraform/envs/$ENV" init -input=false -backend-config="bucket=$PROJECT-tfstate" >/dev/null
export PLATFORM_API_URL="$(terraform -chdir="infra/terraform/envs/$ENV" output -raw platform_api_url)"
```

`uv` is the Python tool the platform uses; the first `platform-cli` command of a session takes a minute while it installs the platform's packages. `platform-cli` signs each request with your own identity token (`gcloud auth print-identity-token`), so it works only for the accounts in that project's `owner_account_ids`.

## Look someone up

The address is read from standard input, so it is not in the command line or in the shell's history. Type it at the prompt:

```bash
read -r -p "Address: " addr
printf '%s\n' "$addr" | platform-cli contact show --email-stdin
unset addr
```

(At the prompt you type, for example, `you@example.org`.) It prints the contact's coded id, whether they are a member, their channels, each entitlement with its id, source, status and end date, and the audit entries.

## Grant by hand and revoke

Give someone the paid tier for a number of months, with a reason you will understand in a year:

```bash
read -r -p "Address: " addr
printf '%s\n' "$addr" | platform-cli grant create --email-stdin --grant tier:paid --months <n> --reason "<why>"
unset addr
```

It prints the new entitlement's id. To end a grant early, use that id (or the one `contact show` prints):

```bash
platform-cli grant revoke --id <entitlement id> --reason "<why>"
```

## Read support requests

```bash
platform-cli support list
```

One line per open request: its id, the member's coded id, the kind, when it was filed and the member's note.

## Run the reconcile by hand

A dry run first, then the counts:

```bash
gcloud run jobs execute stripe-reconcile --project "$PROJECT" --region asia-southeast1 --update-env-vars PLATFORM_JOB_DRY_RUN=1,PLATFORM_JOB_REQUESTED_BY=owner --wait
platform-cli runs show --kind stripe_reconcile
```

For a real run, leave out `PLATFORM_JOB_DRY_RUN=1,`. If the counts surprise you, read [launch.md, section 5](launch.md#5-if-the-paid-counts-do-not-match) before a real run.

## Import a new export

Export the subscriber list from Substack, upload it to Cloud Shell outside the repository folder, then:

```bash
INBOX="$(terraform -chdir="infra/terraform/envs/$ENV" output -raw roster_inbox_bucket)"
gcloud storage cp ~/<export file>.csv "gs://$INBOX/"
gcloud run jobs execute roster-import --project "$PROJECT" --region asia-southeast1 --update-env-vars PLATFORM_JOB_DRY_RUN=1,PLATFORM_JOB_REQUESTED_BY=owner --wait
platform-cli runs show --kind roster_import
```

If the counts look right, run it again without `PLATFORM_JOB_DRY_RUN=1,`, then `rm ~/<export file>.csv`. The import needs a good real reconcile from the last 24 hours; run one first if it refuses.

## Publish or retire a library item

Copy the item folders (each with its manifest and file) to a folder of the staging bucket, then publish, dry run first:

```bash
STAGING="$(terraform -chdir="infra/terraform/envs/$ENV" output -raw library_staging_bucket)"
gcloud storage cp -r <your item folders> "gs://$STAGING/<name>/"
platform-cli library publish --staging-prefix <name> --dry-run
platform-cli library publish --staging-prefix <name>
```

A published file is never overwritten: to change a file, raise the item's `version` in its manifest. To **retire** an item (it leaves the catalogue; members who hold it keep it), copy its folder again with `status: retired` in the manifest, under a new `<name>`, and publish that folder the same way.

## Read the launch report

```bash
platform-cli launch report
```

Counts per campaign and promotion, and the number of members. No addresses.

## Change the reconcile schedule

The schedule is a Terraform setting. Edit `reconcile_schedule` in the root's git-ignored settings file (a cron line in UTC, at least 10 minutes between runs, for example `*/15 * * * *` while a campaign is open), then apply:

```bash
nano "infra/terraform/envs/$ENV/terraform.tfvars"
export TF_VAR_owner_member="user:$(gcloud config get-value account)"
read -rs -p "Cloudflare API token: " TF_VAR_cloudflare_api_token; echo; export TF_VAR_cloudflare_api_token
terraform -chdir="infra/terraform/envs/$ENV" apply
```

The plan should show one update in place, the scheduler job `stripe-reconcile`. To stop the schedule, set `reconcile_schedule_enabled = false` the same way (launch.md, section 4).

## Store a new Stripe key

When you replace the restricted key (for example once a year, or if it may have been seen), create the new one in Stripe as in [launch.md, Gate 2 step 1](launch.md#2-gate-2-dev) (in live mode for prod), then store it and check access:

```bash
bash ops/scripts/40-stripe-key.sh "$PROJECT" --live
bash ops/scripts/41-check-stripe-key-access.sh "$PROJECT"
```

(For dev, leave out `--live`.) The job reads the newest version from its next run. Check with a dry run (above), then disable the old version and delete the old key in Stripe:

```bash
gcloud secrets versions list stripe-read-key --project "$PROJECT"
gcloud secrets versions disable <old version number> --secret stripe-read-key --project "$PROJECT"
```

## Delete a member's account on request

The command arrives with the Core lane's task card C8 and is not available yet. When it is merged: a member asks for deletion from their Account page; you list the waiting requests and delete each one. It removes the member record, the contact record and the entitlements, and writes one audit entry under the coded id.

```bash
platform-cli member deletions
platform-cli member delete --uid <uid>
```
