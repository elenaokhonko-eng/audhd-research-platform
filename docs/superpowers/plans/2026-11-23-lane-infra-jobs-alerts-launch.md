# Lane L3 Infra · Jobs, Permissions, Record Expiry, Alerts and the Launch Runbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everything the second wave's code needs from Google Cloud exists as Terraform in both projects: the two jobs with their own identities, the Stripe key that only one of them can read, the schedule, the settings on each service, automatic expiry of the records the privacy notice gives a lifetime to, alerts for the failures that matter, and the runbook the owner follows at Gate 2 and Gate 3.

**Architecture:** Each new piece is a small Terraform **module** (a reusable folder of resources) with its own test file, used by both roots (`envs/dev`, `envs/prod`). Tests use Terraform's built-in test runner with mock providers, so CI checks the configuration without touching a cloud project. A value that is private (the owner's account id, Substack's application id, what a plan is recorded as) is a Terraform variable set in the git-ignored `terraform.tfvars` of each root, never a default in the repository. The owner applies; this lane never does.

**Tech Stack:** Terraform 1.13 with the `google` provider at the version the roots pin, Bash with `shellcheck`, GitHub Actions.

**Spec:** [contracts](../../contracts/stage-1-launch.md) §6 (settings, jobs, commands) and §7 (infrastructure names) · [08 security and identities](../../architecture/08-security-identities-and-org.md) §3 · the hand-over sections of the [Core](2026-11-20-lane-core-entitlements-and-sign-in.md), [Commerce](2026-11-23-lane-commerce-reconcile-promotions-roster.md), [Library](2026-11-23-lane-library-publish-catalogue-download.md) and [Web](2026-11-23-lane-web-workspace-upgrade-library.md) plans · the privacy notice (`apps/web/content/legal/privacy.md`, "How long we keep it") · task cards I3 to I5.

**Lane rules:** change only `infra/terraform/`, `.github/workflows/`, `ops/scripts/`, `docs/runbooks/` and `services/platform-api/Dockerfile` with `.dockerignore`. Branch `infra/wave-2` from `integration/stage-1`; one pull request per task against it. You never run `terraform apply`, `gcloud` against a real project, or any script in `ops/scripts`: you write them, CI checks them, the owner runs them. Tasks 1 to 4 need nothing from the other lanes. Task 5's workflow change needs the Commerce lane's jobs to exist in the image (Commerce Task 6); write it against the job names of the contracts page and say in the pull request that it deploys them once they exist.

## Global Constraints

- Region `asia-southeast1`. No resource is created by hand. No `allUsers` binding anywhere.
- **Least privilege, stated as exact lists.** Each task's tests assert the complete set of members for the sensitive resources, so an extra binding fails the test.
- **No secret value in Terraform, in state, in a variable or in a workflow.** Terraform creates the secret's container; the owner adds the value from her terminal with a script that reads it without showing it.
- **No private value in the repository:** account ids, Substack's application id, the owner's address, schedule periods chosen for a campaign, grant settings. Each is a variable without a default, or with a neutral default, set in `terraform.tfvars`. Every new variable is added to both roots' `terraform.tfvars.example` with a placeholder and a one-line explanation.
- Every module has `versions.tf` (`required_version >= 1.7`, `required_providers` with sources, at the roots' versions), `variables.tf`, `main.tf`, `outputs.tf` and `tests/<name>.tftest.hcl` with `mock_provider`. Tests use `command = plan` only.
- Both roots get the same change in the same task. A difference between dev and prod is a variable, not a different file.
- Scripts: `set -euo pipefail`; usage on a missing argument with exit code 2; never print a secret, a token or an address; safe to run twice. Each has a test under `ops/scripts/tests/` that runs it against stub commands on `PATH`, as the first wave's scripts do.
- Check commands for every task: `terraform fmt -check -recursive infra/terraform`; in each changed module `terraform init -backend=false && terraform validate && terraform test`; in each root `terraform init -backend=false && terraform validate`; `shellcheck ops/scripts/*.sh ops/scripts/tests/*.sh`; `bash ops/scripts/tests/run-all.sh`.

## Rulings by the integrator

1. **The owner starts the two jobs with `gcloud run jobs execute`** at launch (contracts §6). She therefore needs permission to run those two jobs, and nothing else new.
2. **`platform-api` may run exactly one job, `stripe-reconcile`**, through a custom role that holds only `run.jobs.run` and `run.executions.get` bound on that job. It may not read the Stripe secret, and may not run `roster-import`.
3. **Record expiry is done by Firestore's own time-to-live policies** on a field named `expires_at`, which the code writes when it creates the record. The lifetimes come from the privacy notice: download records and support messages 12 months, access-change records 24 months, rate-limit counters 2 days. This plan creates the policies; the Core and Library lanes write the field (the integrator adds that to their plans and to the contracts page).
4. **The reconcile runs on a schedule set by a variable**, default every 30 minutes; the owner shortens it in `terraform.tfvars` while a campaign is open.

## Review Focus

1. **Who can read the Stripe key.** Exactly one identity. Pinned in Task 1.
2. **What `platform-api` can start.** One job and nothing else. Pinned in Task 1.
3. **A key pasted into the wrong place.** The script refuses a key that is not a restricted key and never echoes it. Pinned in Task 2.
4. **An alert that never fires.** Each alert has a script that raises it on purpose in dev. Pinned in Task 4.
5. **A production deploy without the owner.** The workflow's production jobs run only in the protected environment, on a version tag. Pinned in Task 5.

---

## File Structure

```
infra/terraform/modules/
├─ reconcile_job/        the stripe-reconcile job, its identity, the Stripe secret, who may read it, who may run it, the schedule
├─ roster_job/           the roster-import job, its identity, its read access to the roster inbox, who may run it
├─ firestore_schema/     composite indexes and time-to-live policies
└─ platform_alerts/      log-based metrics and alert policies
infra/terraform/envs/{dev,prod}/   wave2.tf (the four modules), variables.tf, platform.tf, main.tf, outputs.tf, terraform.tfvars.example
ops/scripts/   40-stripe-key.sh  41-check-stripe-key-access.sh  42-raise-test-alert.sh  tests/test-40.sh test-41.sh test-42.sh
.github/workflows/platform-api.yml   deploy the image to the two new jobs as well
docs/runbooks/   launch.md  operations.md
```

---

### Task 1: The two jobs, their identities and the Stripe secret

**Files:**
- Create: `modules/reconcile_job/*`, `modules/roster_job/*`, `envs/{dev,prod}/wave2.tf`
- Modify: `envs/{dev,prod}/variables.tf`, `outputs.tf`, `main.tf` (enable `secretmanager.googleapis.com`, `cloudscheduler.googleapis.com`, `iamcredentials.googleapis.com` if not enabled), `terraform.tfvars.example`

**Interfaces:**
- `modules/reconcile_job` inputs: `project_id`, `region`, `image` (placeholder by default, image changes ignored as for `platform-selfcheck`), `env` (map of plain settings), `api_service_account_email`, `owner_member`, `schedule` (cron, default `*/30 * * * *`), `scheduler_service_account_email`. It creates:
  - the service account `job-reconcile`;
  - the secret `stripe-read-key` (automatic replication is not allowed here: `user_managed` replication in `var.region`), with **no version**;
  - `roles/secretmanager.secretAccessor` on that secret for `job-reconcile` only, with `google_secret_manager_secret_iam_binding` (authoritative for the role, so the member list is exact);
  - the Cloud Run job `stripe-reconcile` (`command = ["platform-cli"]`, `args = ["job", "stripe-reconcile"]`, one task, no retries, timeout 900 seconds, running as `job-reconcile`), with `env` plus `PLATFORM_STRIPE_KEY_SECRET` = the secret's resource name plus `/versions/latest`;
  - a custom project role `platformJobRunner` with exactly `run.jobs.run` and `run.executions.get`, bound **on the job** to `api_service_account_email`, `owner_member` and `scheduler_service_account_email` (one authoritative binding);
  - a Cloud Scheduler job that calls the Run Admin API's `…/jobs/stripe-reconcile:run` with an OAuth token of the scheduler's account, on `schedule`, time zone `Etc/UTC`, with the environment override `PLATFORM_JOB_REQUESTED_BY=schedule` in the request body.
  Outputs: `job_name` (full resource name), `secret_name`, `service_account_email`.
- `modules/roster_job` inputs: `project_id`, `region`, `image`, `env`, `roster_inbox_bucket`, `owner_member`. It creates the service account `job-roster`; `roles/storage.objectViewer` on the roster inbox bucket for it; the job `roster-import` (`args = ["job", "roster-import"]`, timeout 900 seconds); the same custom-role binding on this job for `owner_member` only. Outputs: `job_name`, `service_account_email`.
- In the roots (`wave2.tf`): a service account `scheduler` for Cloud Scheduler; both modules; for **both** job identities the grants the code needs and no more: Firestore user (`roles/datastore.user`), the existing custom role on the contact key, publisher on `platform.events`. The jobs' `env` is `local.platform_common_env` plus `PLATFORM_CONTACT_KEY`, `PLATFORM_STRIPE_SUBSTACK_APPLICATION`, `PLATFORM_SUBSTACK_GRANT_MONTH`, `PLATFORM_SUBSTACK_GRANT_YEAR`, and for the roster job `PLATFORM_ROSTER_INBOX_BUCKET`; dev only: `PLATFORM_STRIPE_TEST_CHANNEL_METADATA = "true"`.
- New root variables (no private default): `stripe_substack_application` (string, default `""`), `substack_grant_month` and `substack_grant_year` (each validated to be `tier:paid` or `status:substack_paid`, default `status:substack_paid`), `reconcile_schedule` (default `*/30 * * * *`).
- New outputs (contracts §7): `stripe_key_secret_name`, `reconcile_job_name`, `roster_import_job_name`.

- [ ] **Step 1: Write the failing tests**

```hcl
# infra/terraform/modules/reconcile_job/tests/reconcile_job.tftest.hcl
mock_provider "google" {}

variables {
  project_id                      = "example-dev"
  region                          = "asia-southeast1"
  env                             = { PLATFORM_ENV = "dev" }
  api_service_account_email       = "platform-api@example-dev.iam.gserviceaccount.com"
  owner_member                    = "user:owner@example.org"
  scheduler_service_account_email = "scheduler@example-dev.iam.gserviceaccount.com"
}

run "only_the_job_reads_the_key" {
  command = plan
  assert {
    condition     = google_secret_manager_secret_iam_binding.readers.role == "roles/secretmanager.secretAccessor"
    error_message = "The binding must be the accessor role."
  }
  assert {
    condition     = google_secret_manager_secret_iam_binding.readers.members == toset(["serviceAccount:job-reconcile@example-dev.iam.gserviceaccount.com"])
    error_message = "Only the reconcile job's identity may read the Stripe key."
  }
}

run "the_secret_stays_in_the_region_and_has_no_version" {
  command = plan
  assert {
    condition     = one(one(google_secret_manager_secret.stripe.replication).user_managed).replicas[0].location == "asia-southeast1"
    error_message = "The secret must be stored in the platform's region."
  }
}

run "the_runner_role_is_two_permissions_on_this_job" {
  command = plan
  assert {
    condition     = toset(google_project_iam_custom_role.job_runner.permissions) == toset(["run.jobs.run", "run.executions.get"])
    error_message = "The runner role may only start a job and read its execution."
  }
  assert {
    condition = google_cloud_run_v2_job_iam_binding.runners.members == toset([
      "serviceAccount:platform-api@example-dev.iam.gserviceaccount.com",
      "user:owner@example.org",
      "serviceAccount:scheduler@example-dev.iam.gserviceaccount.com",
    ])
    error_message = "Exactly the API, the owner and the scheduler may start the reconcile."
  }
}

run "the_job_runs_the_right_command_as_its_own_identity" {
  command = plan
  assert {
    condition     = google_cloud_run_v2_job.this.template[0].template[0].containers[0].args == tolist(["job", "stripe-reconcile"])
    error_message = "The job must run platform-cli job stripe-reconcile."
  }
  assert {
    condition     = google_cloud_run_v2_job.this.template[0].template[0].max_retries == 0
    error_message = "A failed reconcile is not retried blindly; the next schedule runs it."
  }
  assert {
    condition     = contains([for e in google_cloud_run_v2_job.this.template[0].template[0].containers[0].env : e.name], "PLATFORM_STRIPE_KEY_SECRET")
    error_message = "The job needs the name of the secret."
  }
}

run "the_schedule_is_a_variable" {
  command   = plan
  variables { schedule = "*/5 * * * *" }
  assert {
    condition     = google_cloud_scheduler_job.reconcile.schedule == "*/5 * * * *" && google_cloud_scheduler_job.reconcile.time_zone == "Etc/UTC"
    error_message = "The schedule must come from the variable, in UTC."
  }
}
```

```hcl
# infra/terraform/modules/roster_job/tests/roster_job.tftest.hcl
mock_provider "google" {}

variables {
  project_id          = "example-dev"
  region              = "asia-southeast1"
  env                 = { PLATFORM_ENV = "dev" }
  roster_inbox_bucket = "example-dev-roster-inbox"
  owner_member        = "user:owner@example.org"
}

run "only_the_owner_starts_the_import" {
  command = plan
  assert {
    condition     = google_cloud_run_v2_job_iam_binding.runners.members == toset(["user:owner@example.org"])
    error_message = "Only the owner may start the roster import."
  }
}

run "the_job_reads_the_inbox_and_nothing_else" {
  command = plan
  assert {
    condition     = google_storage_bucket_iam_member.reads_inbox.role == "roles/storage.objectViewer" && google_storage_bucket_iam_member.reads_inbox.bucket == "example-dev-roster-inbox"
    error_message = "The import job reads the roster inbox."
  }
  assert {
    condition     = google_cloud_run_v2_job.this.template[0].template[0].containers[0].args == tolist(["job", "roster-import"])
    error_message = "The job must run platform-cli job roster-import."
  }
}
```

- [ ] **Step 2: See them fail**

Run in each module folder: `terraform init -backend=false && terraform test`
Expected: FAIL, no configuration files (the modules do not exist yet).

- [ ] **Step 3: Write the modules and use them in both roots**

Give the job runner role a distinct id per module use if both modules would otherwise create the same custom role: create the role **once** in the root and pass its id to both modules (adjust the reconcile test to read the role from a variable if you do; keep the assertion on its two permissions in a root-level `check` block or in the module that owns it). **Before writing the scheduler job, read the Cloud Scheduler and Cloud Run Admin API documentation** for the `:run` call's body (`overrides.containerOverrides[].env`) and the OAuth scope it needs.

- [ ] **Step 4: See them pass**

Run the check commands. Expected: 5 runs pass in `reconcile_job`, 2 in `roster_job`; both roots validate.

- [ ] **Step 5: Commit**

```bash
git add infra/terraform
git commit -m "infra: reconcile and roster jobs with their own identities; the Stripe secret read by one of them; who may start what"
```

---

### Task 2: The owner's scripts for the Stripe key

**Files:**
- Create: `ops/scripts/40-stripe-key.sh`, `ops/scripts/41-check-stripe-key-access.sh`, `ops/scripts/tests/test-40.sh`, `ops/scripts/tests/test-41.sh`
- Modify: `ops/scripts/tests/run-all.sh` (if the first wave's runner lists tests by name)

**Interfaces:**
- `40-stripe-key.sh <project_id>`: reads the key with `read -rs` (nothing is shown) or from standard input when it is not a terminal; refuses, with exit code 1 and without repeating the value, a key that does not start with `rk_live_` (prod) or `rk_test_` (any other project), and says in plain words that a key starting `sk_` is a full secret key and must never be stored; refuses an empty value; then runs `gcloud secrets versions add stripe-read-key --project <project_id> --data-file=-` with the key on standard input; prints `STORED a new version of stripe-read-key in <project_id>` and the last four characters. A project whose id ends in `-prod` requires `rk_live_`.
- `41-check-stripe-key-access.sh <project_id>`: reads the secret's IAM policy as JSON (`gcloud secrets get-iam-policy … --format=json`) and exits 0 with `ONLY job-reconcile CAN READ THE STRIPE KEY` when the accessor role's members are exactly the reconcile job's service account, and no other role on the secret has members; otherwise exits 1 and prints the roles and how many members each has (never an address of a person; service account names are printed).

- [ ] **Step 1: Write the failing tests**

`tests/test-40.sh` (stub `gcloud` on `PATH` that appends its arguments to `$STUB_LOG` and its standard input to `$STUB_STDIN`), five cases:

1. `printf 'rk_test_abc1234' | 40-stripe-key.sh example-dev` → exit 0; the stub was called with `secrets versions add stripe-read-key --project example-dev --data-file=-`; `$STUB_STDIN` holds the key; the script's own output contains `1234` and does not contain `rk_test_abc`.
2. `printf 'sk_test_abc' | …` → exit 1; the stub was not called; the output mentions "full secret key" and does not contain `sk_test_abc`.
3. `printf 'rk_test_abc' | 40-stripe-key.sh example-prod` → exit 1 (a test key in prod); the stub was not called.
4. `printf '' | …` → exit 1; the stub was not called.
5. No argument → exit 2 and a usage line.

`tests/test-41.sh` (stub `gcloud` that prints the JSON file named by `$STUB_POLICY`), three cases: a policy with the one expected member → exit 0; a policy with a second accessor → exit 1, and the output contains no `@example.org` address of a person; a policy with an extra role (`roles/secretmanager.admin`) → exit 1.

- [ ] **Step 2: See them fail**

Run: `bash ops/scripts/tests/test-40.sh`
Expected: FAIL, the script does not exist.

- [ ] **Step 3: Write both scripts**

- [ ] **Step 4: See them pass**

Run the check commands. Expected: `test-40.sh` reports 5 passed, `test-41.sh` 3 passed; `shellcheck` is clean.

- [ ] **Step 5: Commit**

```bash
git add ops/scripts
git commit -m "ops: store the restricted Stripe key without showing it; check who can read it"
```

---

### Task 3: Indexes, record expiry and the settings of each service

**Files:**
- Create: `modules/firestore_schema/*`
- Modify: `envs/{dev,prod}/wave2.tf`, `platform.tf`, `main.tf` (the web service's settings), `identities.tf`, `variables.tf`, `terraform.tfvars.example`

**Interfaces:**
- `modules/firestore_schema` (input `project_id`, `database` default `(default)`) creates:

| Kind | Collection | Fields |
| --- | --- | --- |
| Composite index | `sync_runs` | `kind` ascending, `finished_at` descending |
| Composite index | `sync_runs` | `kind`, `state`, `dry_run` ascending, `finished_at` descending |
| Composite index | `downloads` | `member_uid` ascending, `at` ascending |
| Composite index | `entitlements` | `status` ascending, `valid_until` ascending |
| Time-to-live policy on `expires_at` | `downloads`, `support_requests`, `audit_log`, `rate_limits` | – |

  Single-field look-ups (`entitlements` by `contact_id`, by `member_uid`, by `source`; `contacts` by `channels.platform.member_uid`) need no resource: Firestore indexes single fields by itself. Say so in a comment, so nobody adds them.
- `platform_api` service settings added: `PLATFORM_OWNER_ACCOUNTS` (`join(",", var.owner_account_ids)`), `PLATFORM_SESSION_TTL_DAYS` (`"14"`), `PLATFORM_LIBRARY_STAGING_BUCKET`, `PLATFORM_RECONCILE_JOB` (the reconcile module's `job_name`). The web service gains `IDENTITY_GOOGLE_ENABLED` (`var.google_sign_in_enabled ? "1" : "0"`).
- New root variables: `owner_account_ids` (list of strings, default `[]`: the Google account ids allowed to call the owner's routes; found with `gcloud auth print-identity-token | cut -d. -f2 | base64 -d 2>/dev/null | jq -r .sub`, which the runbook of Task 5 gives), `google_sign_in_enabled` (bool, default `false`).
- New grant: the owner may call `platform-api` (`roles/run.invoker` on that service for `var.owner_member`), which the owner's `platform-cli` needs. Check `local.platform_api_invokers` first: add the owner there if that is how invokers are given.

- [ ] **Step 1: Write the failing tests**

```hcl
# infra/terraform/modules/firestore_schema/tests/firestore_schema.tftest.hcl
mock_provider "google" {}

variables {
  project_id = "example-dev"
}

run "records_with_a_lifetime_expire_by_themselves" {
  command = plan
  assert {
    condition     = toset(keys(google_firestore_field.expires)) == toset(["downloads", "support_requests", "audit_log", "rate_limits"])
    error_message = "Exactly these collections have a time-to-live policy; the privacy notice names their lifetimes."
  }
  assert {
    condition     = alltrue([for f in google_firestore_field.expires : f.field == "expires_at" && length(f.ttl_config) == 1])
    error_message = "The policy is on the field expires_at."
  }
}

run "the_queries_have_their_indexes" {
  command = plan
  assert {
    condition     = toset([for i in google_firestore_index.this : i.collection]) == toset(["sync_runs", "downloads", "entitlements"])
    error_message = "Composite indexes exist for sync_runs, downloads and entitlements."
  }
  assert {
    condition     = length(google_firestore_index.this) == 4
    error_message = "Four composite indexes, as the plan lists them."
  }
}
```

- [ ] **Step 2: See them fail**

Run: `terraform init -backend=false && terraform test` in the module folder.
Expected: FAIL, no configuration files.

- [ ] **Step 3: Write the module; add the settings, variables and the grant to both roots**

- [ ] **Step 4: See them pass**

Run the check commands. Expected: 2 runs pass; both roots validate; `terraform.tfvars.example` in both roots names every new variable.

- [ ] **Step 5: Commit**

```bash
git add infra/terraform
git commit -m "infra: indexes, time-to-live policies for records with a stated lifetime, settings for the second wave"
```

---

### Task 4: Alerts

**Files:**
- Create: `modules/platform_alerts/*`, `ops/scripts/42-raise-test-alert.sh`, `ops/scripts/tests/test-42.sh`
- Modify: `envs/{dev,prod}/wave2.tf`

**Interfaces:**
- `modules/platform_alerts` (inputs `project_id`, `notification_channel_ids`) creates one log-based metric and one alert policy for each row; each policy notifies the existing owner email channel and its documentation text says what happened and what to do first, in two sentences.

| Name | Fires when | First thing to do (in the alert's text) |
| --- | --- | --- |
| `reconcile-failed` | a log line contains `alert=reconcile_failed` | "The Stripe reconcile could not finish; nothing was changed. Run `platform-cli runs show` and read the job's log." |
| `reconcile-guard-blocked` | `alert=reconcile_guard_blocked` | "A run would have ended many memberships at once and was stopped; nothing was changed. Compare Stripe's subscriber count with the last good run before doing anything." |
| `roster-refused` | `alert=roster_refused` | "The export import refused to run because there is no recent good reconcile. Run the reconcile first." |
| `roster-truncated` | `alert=roster_truncated` | "The export file is incomplete; nothing was applied. Export again from Substack and upload the new file." |
| `api-errors` | `platform-api` answers 5xx to more than 5% of requests over 10 minutes, with at least 20 requests | "The member service is failing. Open its log for the last 15 minutes." |
| `address-in-logs` | a log line of `platform-api`, `platform-hooks` or a job contains an email-shaped string that does not end in `example.org` or `gserviceaccount.com` | "A log line contains what looks like an email address. This must not happen; find the line and tell the integrator." |

  The four marker metrics filter on `resource.type` of Cloud Run services and jobs and on the text of the message (`textPayload` or `jsonPayload.message`). The address filter uses a regular expression for an address and excludes the two domains.
- `42-raise-test-alert.sh <project_id> <name>`: for the four marker alerts and `address-in-logs`, writes one log entry that matches the metric (`gcloud logging write platform-test "<text>" --project … --severity=ERROR`, with the resource labels the filter expects; for `address-in-logs` the text contains `someone@example.com`), prints `WROTE a test entry for <name>; the alert email should arrive within 5 minutes`, and refuses a project whose id ends in `-prod` and any other name (exit 2).

- [ ] **Step 1: Write the failing tests**

```hcl
# infra/terraform/modules/platform_alerts/tests/platform_alerts.tftest.hcl
mock_provider "google" {}

variables {
  project_id               = "example-dev"
  notification_channel_ids = ["projects/example-dev/notificationChannels/1"]
}

run "every_marker_has_a_metric_and_a_policy" {
  command = plan
  assert {
    condition     = toset(keys(google_logging_metric.marker)) == toset(["reconcile-failed", "reconcile-guard-blocked", "roster-refused", "roster-truncated"])
    error_message = "One metric per alert marker the code writes."
  }
  assert {
    condition     = alltrue([for name, m in google_logging_metric.marker : strcontains(m.filter, "alert=${replace(name, "-", "_")}")])
    error_message = "Each metric filters on its own marker."
  }
  assert {
    condition     = toset(keys(google_monitoring_alert_policy.marker)) == toset(keys(google_logging_metric.marker))
    error_message = "Each marker metric has an alert policy."
  }
}

run "every_policy_tells_the_owner_and_says_what_to_do" {
  command = plan
  assert {
    condition = alltrue([
      for p in concat(values(google_monitoring_alert_policy.marker), [google_monitoring_alert_policy.api_errors, google_monitoring_alert_policy.address_in_logs]) :
      p.notification_channels == tolist(["projects/example-dev/notificationChannels/1"]) && length(one(p.documentation).content) > 40
    ])
    error_message = "Every alert notifies the owner's channel and carries its instructions."
  }
}

run "the_address_alert_ignores_test_and_service_addresses" {
  command = plan
  assert {
    condition     = strcontains(google_logging_metric.address_in_logs.filter, "example\\\\.org") && strcontains(google_logging_metric.address_in_logs.filter, "gserviceaccount")
    error_message = "The filter must exclude example.org and service account addresses."
  }
}
```

`tests/test-42.sh` (stub `gcloud`), four cases: `example-dev reconcile-failed` → exit 0 and the stub received `logging write` with a text containing `alert=reconcile_failed`; `example-dev address-in-logs` → the text contains `@example.com`; `example-prod reconcile-failed` → exit 2, the stub not called; `example-dev nonsense` → exit 2.

- [ ] **Step 2: See them fail**

Run: `terraform init -backend=false && terraform test` in the module folder.
Expected: FAIL, no configuration files.

- [ ] **Step 3: Write the module, use it in both roots, write the script**

**Before writing the filters, read the Cloud Logging query language documentation** for regular-expression matching and for how a structured message appears (`jsonPayload.message`); the service's formatter writes one JSON object per line with the key `message`. If the escaping in the third test does not match what the provider needs, fix the test's expected string to the correct one and say so in the pull request.

- [ ] **Step 4: See them pass**

Run the check commands. Expected: 3 runs pass; `test-42.sh` reports 4 passed.

- [ ] **Step 5: Commit**

```bash
git add infra/terraform ops/scripts
git commit -m "infra: alerts for a failed or blocked reconcile, a refused or truncated import, API errors and addresses in logs"
```

---

### Task 5: Deploying the new jobs, and the owner's runbooks

**Files:**
- Modify: `.github/workflows/platform-api.yml`
- Create: `docs/runbooks/launch.md`, `docs/runbooks/operations.md`

**Interfaces:**
- `platform-api.yml`: wherever a deploy job updates the image of `platform-selfcheck`, it also updates `stripe-reconcile` and `roster-import` (`gcloud run jobs update <name> --image …`), skipping a job that does not exist yet with a notice in the log (so the workflow passes before the owner has applied this plan's Terraform). The production job keeps `environment: production` and the tag condition; this task does not change who may deploy.
- `docs/runbooks/launch.md`, written for the owner in the style of the first wave's runbooks (commands first, what each prompt means, "It worked when", "If it stops"). Sections, in order:
  1. **Before Gate 2:** apply this wave's Terraform to dev (`bash ops/scripts/20-stage1-foundations.sh`, what the plan should show); find your account id and put it in `owner_account_ids`; put Substack's application id in `stripe_substack_application` (Gate 2 step 3 finds it).
  2. **Gate 2 (dev):** create the restricted key in the Stripe **sandbox** with read access to customers, subscriptions and invoices only, and store it (`40-stripe-key.sh`); check access (`41-…`); dry-run the reconcile (`gcloud run jobs execute stripe-reconcile --project … --region … --update-env-vars PLATFORM_JOB_DRY_RUN=1,PLATFORM_JOB_REQUESTED_BY=owner --wait`), read the counts (`platform-cli runs show`); raise one test alert (`42-…`) and wait for the email.
  3. **Gate 3 (prod), in this order:** apply Terraform to prod; store the **live** restricted key; check access; set the private values in `terraform.tfvars` (application id, the two grant settings, the schedule) and apply; tag and approve the production deploy; dry-run the reconcile and **compare its paid count with Substack's dashboard**; run it for real; upload the export and dry-run then run the import; `platform-cli campaign apply`, `promo apply`; publish the library (`gcloud storage cp -r …` then `platform-cli library publish`, dry run first); set the terms versions; test with your own two addresses (one paid, one free); only then `platform-cli launch set --join-open true`, and `--library-open true`, `--promotions-open true` when each is ready.
  4. **Closing a layer at once:** the three `launch set … false` commands, and what each hides.
  5. **If the paid counts do not match:** do not run for real; what to look at (`not_substack`, `no_address`, `past_due_unknown` in the run's counts).
- `docs/runbooks/operations.md`: the day-to-day commands with one example each: look someone up (`platform-cli contact show --email-stdin`), grant by hand and revoke, read support requests, run the reconcile by hand, import a new export, publish or retire a library item, read the launch report, change the reconcile schedule, store a new Stripe key, and **delete a member's account on request** (the command the Core lane provides for task card C8; if it is not merged when you write this page, leave the heading with one line saying the command arrives with C8, and tell the integrator).
- Neither runbook contains a real id, price, date or address; examples use `example-dev`, `<your project>` and `you@example.org`.

- [ ] **Step 1: Write the check that fails first**

Add to `ops/scripts/tests/` a test `test-runbooks.sh` that fails unless: `docs/runbooks/launch.md` and `operations.md` exist; every `ops/scripts/NN-*.sh` named in them exists; every `platform-cli` subcommand named in them is one of the commands of contracts §6 (keep the list in the test); and neither file contains an address outside `example.org`, a string starting `rk_live_` or `sk_`, or a 12-digit project number.

- [ ] **Step 2: See it fail**

Run: `bash ops/scripts/tests/test-runbooks.sh`
Expected: FAIL, `docs/runbooks/launch.md` does not exist.

- [ ] **Step 3: Write the two runbooks and the workflow change**

- [ ] **Step 4: See it pass**

Run the check commands and `actionlint .github/workflows/platform-api.yml` if the repository's CI runs it. Expected: `test-runbooks.sh` passes; the workflow file is valid.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows docs/runbooks ops/scripts
git commit -m "infra: deploy the image to the new jobs; launch and operations runbooks for the owner"
```

---

## Exit test for this plan

1. CI passes on every pull request of the lane: format, validate, module tests, script tests, shellcheck.
2. A search of the lane's diff finds no account id, application id, key, address outside `example.org`, or schedule other than the neutral default.
3. The hand-over lists, as commands, exactly what the owner runs before Gate 2 and at Gate 2, with the expected plan summary for each apply (what is created; that nothing is destroyed).
4. The hand-over tells the integrator which hand-over items of the other lanes' plans this plan did **not** cover, if any.
