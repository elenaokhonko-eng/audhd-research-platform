# Launch runbook: the jobs, the Stripe key, Gate 2 and Gate 3

Everything below runs in **Google Cloud Shell**, from the repository root (`~/audhd-research-platform`), after the foundations and sign-in runbooks ([stage-1-foundations.md](stage-1-foundations.md), [stage-1-sign-in.md](stage-1-sign-in.md)) and Gate 1. Do the sections in order. Every command can be run again safely unless the step says otherwise.

Terms used below:

- **The reconcile** is the Cloud Run job `stripe-reconcile`. It reads every subscription in Stripe with a **restricted key** (a Stripe key that can only read the three kinds of object it is given) and records who pays through Substack. It runs on a schedule (Cloud Scheduler), created **paused**.
- **The roster import** is the job `roster-import`. It reads the newest subscriber export you placed in the roster inbox bucket and records paying readers that Stripe does not know about (gift, complimentary, billed by Apple).
- **A dry run** is a run of a job that works everything out, writes its own run record with the counts, and changes nothing else. Only your account may start a job with a dry-run setting.
- **`platform-cli`** is the platform's command line. It calls the owner's routes of `platform-api` with your own identity token. Set it up once per Cloud Shell session as in [operations.md, "Before any command"](operations.md#before-any-command).
- **The layers** are three switches in Firestore (`config/launch`): `join_open` (new people may sign in and join), `library_open` and `promotions_open`. All three start closed.

What this costs: nothing while idle. The two jobs are billed per second while they run (a few cents a month at a 30-minute schedule); the scheduler job, the secret, the log metrics and the alert policies stay inside Google's free tiers.

## 1. Before Gate 2: apply this wave's Terraform to dev only

Do not run `20-stage1-foundations.sh` for this: it applies prod first. Here only dev changes.

**a. Set up the shell.** Terraform needs your account and the Cloudflare token, as in the foundations runbook. Nothing is shown while you paste the token, and it is not saved anywhere:

```bash
cd ~/audhd-research-platform
git fetch origin && git checkout integration/stage-1 && git pull
export TF_VAR_owner_member="user:$(gcloud config get-value account)"
read -rs -p "Cloudflare API token: " TF_VAR_cloudflare_api_token; echo; export TF_VAR_cloudflare_api_token
terraform -chdir=infra/terraform/envs/dev init -input=false -backend-config="bucket=audhd-neurobiology-dev-tfstate"
```

**b. Find your account id.** Your Google account has a number that never changes, the `sub` of your identity token. `platform-api` lets only the account ids in `owner_account_ids` call the owner's routes. The foundations script does not write this setting, so you add it:

```bash
gcloud auth print-identity-token | python3 -c 'import sys,json,base64; p=sys.stdin.read().split(".")[1]; print(json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))["sub"])'
```

It prints one long number. Check the settings file is ignored by git (the command prints its path) and that the two settings are not there yet (it prints nothing):

```bash
git check-ignore infra/terraform/envs/dev/terraform.tfvars
grep -nE '^(owner_account_ids|stripe_substack_application)' infra/terraform/envs/dev/terraform.tfvars
```

Then append the id (a setting may appear only once in the file; if the `grep` printed it, edit that line instead with `nano infra/terraform/envs/dev/terraform.tfvars`):

```bash
cat >> infra/terraform/envs/dev/terraform.tfvars <<'EOF'
owner_account_ids = ["<the number printed>"]
EOF
```

`stripe_substack_application` (Substack's application id in Stripe) stays empty in dev: the Stripe sandbox cannot make a subscription "created by Substack", so dev treats a sandbox subscription with the metadata `test_channel=substack` as one. Gate 2, step 3 finds the real id, for prod.

**c. Apply:**

```bash
terraform -chdir=infra/terraform/envs/dev apply
```

| Prompt | Answer |
| --- | --- |
| `Do you want to perform these actions?` | Read the plan against the list below. Type `yes` to apply; anything else cancels and nothing changes. |

What the plan should show, all in the dev project:

- **Create:** the Cloud Scheduler API switched on; the service accounts `job-stripe` (the reconcile), `job-substack` (the roster import) and `scheduler`; the custom roles `platformJobRunner` (start a job and follow its runs, nothing else) and `platformSignInManager` (sessions and accounts of sign-in); the secret `stripe-read-key` **without a version** (the key itself is added by you in Gate 2, never by Terraform); the jobs `stripe-reconcile` and `roster-import`, with Google's placeholder image; the scheduler job `stripe-reconcile`, **paused**; the Firestore indexes (on `sync_runs`, `downloads`, `entitlements`, `audit_log`) and the time-to-live fields `expires_at` (on `downloads`, `support_requests`, `audit_log`, `rate_limits`); the log-based metrics `platform-alert-...` and the alert policies `Platform alert: ...`; and IAM bindings: `job-stripe` alone on the secret, who may start each job, your account on the two jobs (start, and start with changed settings), your account as an invoker of `platform-api`, `platform-api`'s sign-in role, the two jobs' access to Firestore, the contact key and the events topic, `job-substack`'s read access to the roster inbox, and the deploy identity acting as `job-stripe` and `job-substack` (so the deploy workflow can give the jobs their image).
- **Update in place:** `platform-api` (new settings: `PLATFORM_OWNER_ACCOUNTS`, `PLATFORM_SESSION_TTL_DAYS`, `PLATFORM_LIBRARY_STAGING_BUCKET`, `PLATFORM_RECONCILE_JOB`) and `web-dev` (`IDENTITY_GOOGLE_ENABLED`).
- **Destroy:** nothing. If the plan destroys anything, answer `no` and report it.

**d. Give the jobs the real image.** The deploy workflow puts the platform's image on `platform-api`, `platform-hooks` and the three jobs; it skipped the two new jobs while they did not exist. Run it once by hand:

```bash
gh workflow run platform-api.yml --ref integration/stage-1
gh run watch "$(gh run list --workflow platform-api.yml --branch integration/stage-1 --limit 1 --json databaseId -q '.[0].databaseId')"
```

The jobs work only once the Commerce lane's job code is merged on `integration/stage-1`; until then a run of either job fails with "unknown job".

**It worked when:**

- Terraform ends with `Apply complete!`, and a second `terraform -chdir=infra/terraform/envs/dev plan` says `No changes`.
- The schedule is paused (prints `PAUSED`):
  ```bash
  gcloud scheduler jobs describe stripe-reconcile --location asia-southeast1 --project audhd-neurobiology-dev --format='value(state)'
  ```
- The secret has no version yet (prints `Listed 0 items.`):
  ```bash
  gcloud secrets versions list stripe-read-key --project audhd-neurobiology-dev
  ```
- Both jobs carry the registry's image, not `us-docker.pkg.dev/cloudrun/container/hello`:
  ```bash
  for j in stripe-reconcile roster-import; do
    gcloud run jobs describe "$j" --region asia-southeast1 --project audhd-neurobiology-dev --format='value(spec.template.spec.template.spec.containers[0].image)'
  done
  ```

**If it stops:**

| Message | What to do |
| --- | --- |
| A Firestore index or field fails with `409`, `Aborted` or "too much contention" | Firestore builds indexes and time-to-live policies one at a time per database, and Terraform asks for several at once. Run the same `apply` again; it continues where it stopped. |
| An alert policy fails with "metric ... not found" or "Cannot find metric" | A new log-based metric takes a minute or two to become visible to Monitoring. Wait two minutes and run the same `apply` again. |
| `Error acquiring the state lock` | As in the foundations runbook, "If it stops". |
| The workflow's log says `The job ... does not exist ... yet` | The apply did not finish. Apply again, then rerun the workflow. |

## 2. Gate 2 (dev)

**1. Create the restricted key in the Stripe sandbox.** In the Stripe Dashboard, switch to your **sandbox** (test data), then Developers, API keys, **Create restricted key**. Name it `platform reconcile (read only)`. Give **Read** to Customers, Subscriptions and Invoices, and **None** to everything else. Create it and leave the page open; Stripe shows the key once.

**Optional, before you store it: see the job-failed alert.** A run before the key is stored fails, and its failure is the alert `Platform alert: job-failed`:

```bash
gcloud run jobs execute stripe-reconcile --project audhd-neurobiology-dev --region asia-southeast1 --update-env-vars PLATFORM_JOB_DRY_RUN=1,PLATFORM_JOB_REQUESTED_BY=owner --wait
```

The command ends with an error (expected). Within about 10 minutes an email "Platform alert: job-failed" arrives (an email "Platform alert: reconcile-failed" may come too). This is the only way to see that alert on purpose.

**2. Store the key and check who can read it:**

```bash
bash ops/scripts/40-stripe-key.sh audhd-neurobiology-dev
bash ops/scripts/41-check-stripe-key-access.sh audhd-neurobiology-dev
```

| Prompt | Answer |
| --- | --- |
| `Restricted Stripe key (starts ...; typed without echo):` | Paste the sandbox key and press Enter. Nothing is shown. The script refuses a full secret key and a live key, and stores nothing then. |

It worked when the first script prints `STORED a new version of stripe-read-key in audhd-neurobiology-dev` and the key's last four characters (compare them with the Dashboard), and the second prints `ONLY job-stripe IS GRANTED ON THE SECRET`. The second also lists, as information, how many members hold project-wide roles that can read every secret (Owner, Secret Manager Admin): that is you.

**Who can reach the key, plainly.** The secret lets one identity read it: `job-stripe`, the reconcile job's own account. `platform-api` cannot read it. But code that runs **as** `job-stripe` can, and two other identities can choose what runs as `job-stripe`:

- **You**, as the project's owner.
- **The deploy identity** of GitHub Actions. It holds the role Cloud Run Developer on the whole project, so it can put a new image on the job, and it can also start any job **with changed settings** (Cloud Run checks that permission on the project as well as on the job). The binding that gives only you the right to start a job with changed settings is on the two jobs; the deploy identity's project-wide role reaches past it.

So the key is as safe as the deploy path: dev deploys come only from the branch `integration/stage-1`, production deploys only from a `v` tag after your approval in GitHub.

**3. Find Substack's application id (for prod).** Substack creates its subscriptions in your Stripe account through a Stripe application; every one of them carries that application's id, a value starting `ca_`. Reading it changes nothing. In the Stripe Dashboard in **live** mode, open Subscriptions, open one subscription you know a reader started on Substack, and read its `application` field (in Workbench's inspector for that subscription, or in the JSON of its creation event under Developers, Events). Write it into **prod's** settings file only, after the same check as section 1 b (with `envs/prod`):

```bash
git check-ignore infra/terraform/envs/prod/terraform.tfvars
grep -nE '^(owner_account_ids|stripe_substack_application)' infra/terraform/envs/prod/terraform.tfvars
cat >> infra/terraform/envs/prod/terraform.tfvars <<'EOF'
stripe_substack_application = "<the application id>"
owner_account_ids = ["<the number printed in section 1 b>"]
EOF
```

Nothing changes in prod until Gate 3 applies it. The id is never written to a file of the repository.

**4. Dry-run the reconcile and read the counts.** Give a few sandbox subscriptions the metadata `test_channel=substack` first (Dashboard, the subscription, Metadata), so dev has something that counts as Substack's. Then:

```bash
gcloud run jobs execute stripe-reconcile --project audhd-neurobiology-dev --region asia-southeast1 --update-env-vars PLATFORM_JOB_DRY_RUN=1,PLATFORM_JOB_REQUESTED_BY=owner --wait
platform-cli runs show --kind stripe_reconcile
```

`--update-env-vars` changes the settings of this one run only; the job keeps its own. It worked when `gcloud` ends with the execution `has successfully completed`, and the latest run shows `dry_run` true, `requested_by` owner, the guard's decision and counts by action that match the sandbox subscriptions you marked. Section 5 explains the counts.

**5. Raise one test alert and wait for the email:**

```bash
bash ops/scripts/42-raise-test-alert.sh audhd-neurobiology-dev reconcile-guard-blocked
```

It worked when it prints `WROTE a test entry for reconcile-guard-blocked; the alert email should arrive within 5 minutes`, and an email "Platform alert: reconcile-guard-blocked" arrives at the alert address within about 10 minutes. The other names it takes are `reconcile-failed`, `roster-refused`, `roster-truncated` and `address-in-logs`; each raises its own alert the same way.

What the test entry proves and what it does not:

- It proves that the alert policy fires and that its email reaches you. The script writes to a test log (`platform-test`) that the alerts accept in dev only, because `gcloud` cannot write an entry that looks as if it came from a Cloud Run job. That a real job's log line raises the alert is proven by a real run in dev that writes one: the optional failed run in step 1, and the Quality lane's failure journeys in Wave 3.
- **The address alert does not fire on invented addresses at `example.org`.** Check it once; no email should arrive within 15 minutes:
  ```bash
  gcloud logging write platform-test "Negative check: contact you@example.org" --project audhd-neurobiology-dev --severity=ERROR
  ```
- **The API-errors alert** ("Platform alert: api-errors", more than 5% of at least 20 requests to `platform-api` answered with a server error over 10 minutes) cannot be raised on purpose. When it fires, read the failing requests (method and status only):
  ```bash
  gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="platform-api" AND httpRequest.status>=500' --project audhd-neurobiology-dev --freshness=1h --limit 20 --format='value(timestamp,httpRequest.requestMethod,httpRequest.status)'
  ```
  and the alert's own page: Cloud console, Monitoring, Alerting, the incident.

To see that every metric exists: `gcloud logging metrics list --project audhd-neurobiology-dev --format='value(name)'` lists the five `platform-alert-...` names.

**If it stops:**

| Message | What to do |
| --- | --- |
| `40-stripe-key.sh`: a refusal | Read it: it says why nothing was stored (a full secret key, a live key, a cut-off paste). Re-run with the right key. |
| `41-...`: `ACCESS IS WIDER THAN job-stripe ALONE` | Someone added a binding on the secret by hand. Do not remove it by hand: report it; the fix is in Terraform. |
| The dry run fails with `PERMISSION_DENIED` on the overrides | Your account lacks the right to start a run with changed settings: the apply of section 1 did not finish. Apply again. |
| The dry run fails with "unknown job" | The Commerce lane's job code is not in the image yet (section 1 d). |
| `platform-cli` says the account is not allowed | `owner_account_ids` in dev's settings file is not your id, or dev was not applied after you added it. |

## 3. Gate 3 (prod)

Do the steps in this order. Before you start, the whole member journey must already have been tested **in dev**: the Quality lane's journeys and your own two addresses (one paid, one free). In prod, a new address cannot sign in while the join layer is closed, so prod gets only the short check of step 11.

**1. Apply Terraform to prod.** In the same shell setup as section 1 a (the token and `TF_VAR_owner_member`), with prod's state:

```bash
terraform -chdir=infra/terraform/envs/prod init -input=false -backend-config="bucket=audhd-neurobiology-prod-tfstate"
terraform -chdir=infra/terraform/envs/prod apply
```

The plan should show what section 1 c lists, in the prod project, with two differences: the platform's services are updated in place in prod (`platform-api` and `web-prod`), and the jobs are created with delete protection. Nothing is destroyed. The schedule is created paused. If it stops with a Firestore `409` or "metric not found", apply again, as in section 1. Then give the jobs the real image: they get it with the production deploy of step 5.

**2. Store the live restricted key.** In the Stripe Dashboard in **live** mode, create a restricted key exactly as in Gate 2 step 1 (Read on Customers, Subscriptions, Invoices; None elsewhere). Then:

```bash
bash ops/scripts/40-stripe-key.sh audhd-neurobiology-prod --live
```

| Prompt | Answer |
| --- | --- |
| `This stores a key for real money. Type the project id again to continue:` | `audhd-neurobiology-prod`. Anything else stops the script; nothing is stored. |
| `Restricted Stripe key (...):` | Paste the live restricted key. The script accepts only a live restricted key here. |

**3. Check access:**

```bash
bash ops/scripts/41-check-stripe-key-access.sh audhd-neurobiology-prod
```

It worked when it prints `ONLY job-stripe IS GRANTED ON THE SECRET`. "Who can reach the key" in Gate 2 step 2 holds for prod too.

**4. Set the private values and apply.** These are your commercial decisions; they live only in prod's git-ignored settings file. Check which are there already:

```bash
grep -nE '^(stripe_substack_application|substack_grant_month|substack_grant_year|reconcile_schedule|reconcile_schedule_enabled|owner_account_ids)' infra/terraform/envs/prod/terraform.tfvars
```

Add the missing ones, or edit their lines (`nano infra/terraform/envs/prod/terraform.tfvars`):

```hcl
stripe_substack_application = "<the application id from Gate 2 step 3>"
substack_grant_month        = "<tier:paid or status:substack_paid>"
substack_grant_year         = "<tier:paid or status:substack_paid>"
reconcile_schedule          = "<cron, UTC, at least 10 minutes apart; */30 * * * * by default>"
reconcile_schedule_enabled  = false
```

`tier:paid` records a paying Substack reader on that plan as a paid member of the platform; `status:substack_paid` records only that they pay, which unlocks nothing by itself and satisfies a campaign's grant policy. Then:

```bash
terraform -chdir=infra/terraform/envs/prod apply
```

The plan should show only the two jobs updated in place (their settings). Nothing is created or destroyed.

**5. Tag and approve the production deploy.** A tag starting with `v` on the commit of `main` you want deploys both the website and the platform, after your approval:

```bash
git fetch origin
git tag -a v<version> origin/main -m "Launch"
git push origin v<version>
```

Then approve both waiting runs (`web` and `platform-api`): GitHub, the repository, Actions, each run, **Review deployments**, tick `production`, **Approve and deploy**. It worked when both runs are green and the two jobs carry the registry's image (the command of section 1, "It worked when", with `audhd-neurobiology-prod`).

**6. Dry-run the reconcile and compare its paid count with Substack's dashboard:**

```bash
gcloud run jobs execute stripe-reconcile --project audhd-neurobiology-prod --region asia-southeast1 --update-env-vars PLATFORM_JOB_DRY_RUN=1,PLATFORM_JOB_REQUESTED_BY=owner --wait
platform-cli runs show --kind stripe_reconcile
```

(`platform-cli` pointed at prod: [operations.md, "Before any command"](operations.md#before-any-command).) Compare the number of paying Substack subscriptions the run found with the paid subscriber count in Substack's dashboard. Readers who do not pay through Stripe (gift, complimentary, billed by Apple) are in Substack's count and not in Stripe; they come in with the roster import. If the numbers do not match after allowing for them, **stop** and follow section 5.

**7. Run it for real:**

```bash
gcloud run jobs execute stripe-reconcile --project audhd-neurobiology-prod --region asia-southeast1 --update-env-vars PLATFORM_JOB_REQUESTED_BY=owner --wait
platform-cli runs show --kind stripe_reconcile
```

It worked when the latest run shows `dry_run` false, the guard passed, and the counts match the dry run's.

**8. Import the export.** Export the subscriber list from Substack (Settings, Export) to your computer, upload it to Cloud Shell (the three dots, Upload), and keep it **outside** the repository folder. Then:

```bash
INBOX="$(terraform -chdir=infra/terraform/envs/prod output -raw roster_inbox_bucket)"
gcloud storage cp ~/<export file>.csv "gs://$INBOX/"
gcloud run jobs execute roster-import --project audhd-neurobiology-prod --region asia-southeast1 --update-env-vars PLATFORM_JOB_DRY_RUN=1,PLATFORM_JOB_REQUESTED_BY=owner --wait
platform-cli runs show --kind roster_import
```

If the dry run's counts look right, run it for real, then delete your copy (the inbox deletes its own after seven days):

```bash
gcloud run jobs execute roster-import --project audhd-neurobiology-prod --region asia-southeast1 --update-env-vars PLATFORM_JOB_REQUESTED_BY=owner --wait
platform-cli runs show --kind roster_import
rm ~/<export file>.csv
```

The import refuses to write unless a real reconcile completed and passed its guard in the last 24 hours; if it refuses, repeat step 7 first. A file cut off mid-row applies nothing; export again.

**9. Write the campaigns and the promotions.** Keep the two files in your private folder, never in the repository:

```bash
platform-cli campaign apply --file <your private folder>/campaigns.yaml
platform-cli promo apply --file <your private folder>/promotions.yaml
```

Each prints what it wrote, or names the field it refused.

**10. Publish the library**, dry run first:

```bash
STAGING="$(terraform -chdir=infra/terraform/envs/prod output -raw library_staging_bucket)"
gcloud storage cp -r <your item folders> "gs://$STAGING/<name>/"
platform-cli library publish --staging-prefix <name> --dry-run
platform-cli library publish --staging-prefix <name>
```

`<name>` is any folder name you choose for this batch. Each item prints one line: published, or refused with the reason.

**11. Set the terms versions, then test in prod.** The versions are the `version:` lines of the two texts as merged:

```bash
grep -m1 '^version:' apps/web/content/legal/terms.md apps/web/content/legal/privacy.md
platform-cli launch set --terms-version <terms version> --privacy-version <privacy version> --substack-account-url <your publication's account page>
```

Then open the join layer and test at once, before any invitation is sent:

```bash
platform-cli launch set --join-open true
```

Sign in on `https://audhdneurobiology.org` with your own two addresses, one that pays on Substack and one that does not. Check what each sees: the paid one the paid workspace and the reasons on the Account page, the free one the free workspace and the upgrade route. If anything is wrong, close the layer again at once (`platform-cli launch set --join-open false`) and report what you saw.

If you do not want to keep the two test members, ask for deletion from each account's Account page, then remove them:

```bash
platform-cli member deletions
platform-cli member delete --uid <uid>
```

These two commands arrive with the Core lane's task card C8; until it is merged, leave the test members in place.

**12. Open the other layers when each is ready**, and switch on the schedule:

```bash
platform-cli launch set --library-open true
platform-cli launch set --promotions-open true
```

Then set `reconcile_schedule_enabled = true` in `infra/terraform/envs/prod/terraform.tfvars` and apply once more:

```bash
terraform -chdir=infra/terraform/envs/prod apply
```

The plan should show one update in place, the scheduler job (`paused` from true to false). It worked when `gcloud scheduler jobs describe stripe-reconcile --location asia-southeast1 --project audhd-neurobiology-prod --format='value(state)'` prints `ENABLED`, and after one period `platform-cli runs show --kind stripe_reconcile` shows a run with `requested_by` schedule.

## 4. Closing a layer, stopping the schedule, going back

**Closing a layer at once.** Each command takes effect on the next request; nothing is deleted:

```bash
platform-cli launch set --join-open false
platform-cli launch set --library-open false
platform-cli launch set --promotions-open false
```

| Switch | What closing it hides |
| --- | --- |
| `--join-open false` | A person who is not a member yet cannot sign in, and the join pages say "opening soon". Existing members still sign in. |
| `--library-open false` | The library: its pages and its downloads, for every member. |
| `--promotions-open false` | Every promotion, everywhere: the upgrade page shows no offer. |

**Stopping the schedule.** Set `reconcile_schedule_enabled = false` in the root's `terraform.tfvars` and apply. Pausing it with `gcloud scheduler jobs pause` also works for a moment, but the next apply switches it on again.

**Going back to the previous version.** Re-run the deploy workflows of the previous tag; each re-run needs your approval again:

```bash
gh run list --workflow platform-api.yml --branch v<previous version> --limit 1
gh run list --workflow web.yml --branch v<previous version> --limit 1
gh run rerun <run id>
```

GitHub re-runs a run only within 30 days. For an older version, tag its commit again under a new version (`git tag -a v<new version> v<previous version>^{commit} -m "Back to v<previous version>"`, then push the tag) and approve as in Gate 3 step 5.

A deploy that failed halfway leaves the services and the jobs on different images. Running the workflow again for the same tag (`gh run rerun <run id>`) puts the same image on all of them.

## 5. If the paid counts do not match

**Do not run the reconcile for real.** Nothing has changed yet: a dry run writes only its own run record. Read the counts of the latest dry run:

```bash
platform-cli runs show --kind stripe_reconcile
```

| Count | Means | What to look at |
| --- | --- | --- |
| `not_substack` | Subscriptions in the Stripe account that were not created by Substack's application | If nearly every subscription is here and few are paid, the application id is wrong or empty: check `stripe_substack_application` in prod's settings file against Gate 2 step 3, apply, and dry-run again |
| `no_address` | Substack's subscriptions whose Stripe customer has no address | Nothing is recorded for them. Look them up in Stripe; after review, grant by hand ([operations.md](operations.md#grant-by-hand-and-revoke)) |
| `past_due_unknown` | Overdue subscriptions whose unpaid invoice date is unknown | Skipped on purpose: nothing ends on missing information. They keep what they had; look at them in Stripe |
| `bad_address`, `incomplete` | An address that cannot be read; a subscription whose first payment never completed | Nothing is recorded for them; look at them in Stripe |

Then compare again: Substack's paid count, minus readers not billed through Stripe (the export's rows with an empty plan), should equal the paying subscriptions the run found. If the guard blocked a run (an email "Platform alert: reconcile-guard-blocked"), never force it: compare Stripe's subscriber count with the last good run, and report what you find.
