# Lane L3 Infra · Identity, Sending Domain, Contact Key and Buckets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the owner's Gate 1 run, the dev and prod projects have email-link and Google sign-in, sign-in emails that come from the platform's own domain, the key that turns an email into a contact id, and three private buckets, all under the names the other lanes read.

**Architecture:** Three small Terraform modules (`identity`, `contact_key`, `private_bucket`) used by both environment roots, each with a `terraform test` file that runs on mocked providers. Two settings that the Terraform provider cannot express (the email sender's domain, the Google sign-in client) are applied by owner-run scripts that call the Identity Toolkit Admin API; the scripts are idempotent and print what they changed.

**Tech Stack:** Terraform >= 1.7 (`terraform test`, `mock_provider`), google ~> 6.10, cloudflare ~> 4.40; bash with `set -euo pipefail`, `gcloud`, `curl`, `jq`; shellcheck.

**Spec:** [launch design](../specs/2026-11-19-launch-invites-grants-promotions-design.md) §5.2, §6, §8, §9 (decision 5) · [contracts](../../contracts/stage-1-launch.md) §6, §7 · `docs/architecture/08-security-identities-and-org.md` §3, §4 · ADR 0020.

**Order in the lane:** this plan starts when tasks 6 to 8 of the [S1.0 plan](2026-11-16-stage-1-slice-0-platform-skeleton.md) are done, because it adds to the two environment roots they create. Branch from `integration/stage-1`; one pull request per task.

## Global Constraints

- Region for every regional resource: `asia-southeast1`. Bucket location: `ASIA-SOUTHEAST1`.
- The agent never runs `terraform apply`, `gcloud` against a real project, or any script in `ops/scripts/`. It writes them; the owner runs them. CI is the agent's check: `terraform fmt -check -recursive`, `terraform validate` per root, `terraform test` per module, `shellcheck`.
- No value that identifies a person or an account is committed: no email address, no OAuth client id or secret, no Cloudflare zone id. Such values arrive at apply time as `TF_VAR_...` environment variables or are typed at a prompt.
- No secret enters Terraform state. The Google sign-in client secret goes from the owner's terminal straight to the Identity Toolkit API.
- Every bucket: uniform bucket-level access, public access prevention `enforced`.
- Identity Platform request logging stays **off**: those logs would contain email addresses.
- Every identity keeps to the permissions manifest: bindings are written in `envs/<env>/identities.tf` and nowhere else. A module returns names; the root binds.
- Output names are a contract ([contracts §7](../../contracts/stage-1-launch.md)): `library_bucket`, `library_staging_bucket`, `roster_inbox_bucket`, `contact_key_name`, `auth_email_domain`, plus `identity_api_key` and `identity_auth_domain` added by this plan.
- The sending domain is `var.domain` in prod and `dev.${var.domain}` in dev.
- Every module has its own `versions.tf`: `required_version = ">= 1.7"` and a `required_providers` block naming each provider it uses with its source, at the versions of the root (`google = { source = "hashicorp/google", version = "~> 6.10" }`; in `sending_domain` also `cloudflare = { source = "cloudflare/cloudflare", version = "~> 4.40" }`). Without it, `cloudflare` resolves to `hashicorp/cloudflare` and `terraform init` fails. The `{main,variables,outputs}.tf` in each task's file list includes this file.
- Each module enables the API it needs with a `google_project_service` (`disable_on_destroy = false`).

## Review Focus

1. **A bucket readable by the public.** No bucket may be created without public access prevention. Pinned in Task 3 for every instance.
2. **The contact key destroyed or rotated.** Either would change every contact id. No rotation period is pinned by a test in Task 2; `prevent_destroy` cannot be asserted by `terraform test`, so the task reviewer confirms it in the diff.
3. **A second SPF record on the sending domain.** A domain may carry one `v=spf1` record; a second one breaks authentication for both senders. One record, built from a list. Pinned in Task 4.
4. **The owner's email address or the OAuth secret reaching the repository, the plan output in CI, or state.** Variables are marked `sensitive`, have no default, and the scripts read secrets with `read -s`. Pinned in Tasks 3, 5 and 6.
5. **Running a script twice.** Each script reads the current setting first and changes nothing when it already matches. Pinned in Tasks 5 and 6 by a dry-run mode that the tests exercise against a stub.

---

## File Structure

```
infra/terraform/
├─ modules/identity/{main,variables,outputs}.tf          Identity Platform config
├─ modules/identity/tests/identity.tftest.hcl
├─ modules/contact_key/{main,variables,outputs}.tf       key ring and MAC key
├─ modules/contact_key/tests/contact_key.tftest.hcl
├─ modules/private_bucket/{main,variables,outputs}.tf    one private bucket
├─ modules/private_bucket/tests/private_bucket.tftest.hcl
├─ modules/sending_domain/{main,variables,outputs}.tf    DNS records for the sign-in email's domain
├─ modules/sending_domain/tests/sending_domain.tftest.hcl
└─ envs/{dev,prod}/members.tf                            uses the four modules; identities.tf gains bindings
ops/scripts/30-auth-email-domain.sh                      owner: verify and apply the sending domain
ops/scripts/31-google-sign-in.sh                         owner: store the Google sign-in client
ops/scripts/tests/{stub-curl.sh,test-30.sh,test-31.sh}   dry-run tests against a stub
docs/runbooks/stage-1-sign-in.md                         the owner's steps, as commands
.github/workflows/terraform.yml                          adds terraform test and shellcheck
```

---

### Task 1: Identity Platform configuration

**Files:**
- Create: `infra/terraform/modules/identity/{main,variables,outputs}.tf`, `infra/terraform/modules/identity/tests/identity.tftest.hcl`, `infra/terraform/envs/dev/members.tf`, `infra/terraform/envs/prod/members.tf`
- Modify: `.github/workflows/terraform.yml` (run `terraform test` in every module directory that has a `tests/` folder; add `ops/scripts/**` to both `paths` filters, so that Tasks 5 and 6 are checked)

**Interfaces:**
- Consumes: `var.project_id`, `var.domain` of each root (they exist).
- Produces: `module "identity"` with inputs `project_id` (string), `authorized_domains` (list of string); outputs `api_key` (sensitive), `auth_domain` (string, `<firebase_subdomain>.firebaseapp.com`). Root outputs `identity_api_key` (sensitive) and `identity_auth_domain`.

- [ ] **Step 1: Write the failing test**

```hcl
# infra/terraform/modules/identity/tests/identity.tftest.hcl
mock_provider "google" {}

variables {
  project_id         = "example-dev"
  authorized_domains = ["dev.example.org"]
}

run "email_link_sign_in_is_on_and_passwords_are_not_required" {
  command = plan
  assert {
    condition     = google_identity_platform_config.this.sign_in[0].email[0].enabled == true
    error_message = "Email sign-in must be enabled."
  }
  assert {
    condition     = google_identity_platform_config.this.sign_in[0].email[0].password_required == false
    error_message = "Email-link sign-in needs password_required = false."
  }
  assert {
    condition     = google_identity_platform_config.this.sign_in[0].allow_duplicate_emails == false
    error_message = "One account per email."
  }
}

run "only_the_given_domains_are_authorised" {
  command = plan
  assert {
    condition     = toset(google_identity_platform_config.this.authorized_domains) == toset(["dev.example.org", "example-dev.firebaseapp.com"])
    error_message = "authorized_domains must be the input list plus the project's own sign-in handler domain, and nothing else (no localhost)."
  }
}

run "request_logging_is_off_and_clients_cannot_delete_accounts" {
  command = plan
  assert {
    condition     = google_identity_platform_config.this.monitoring[0].request_logging[0].enabled == false
    error_message = "Identity request logs would contain email addresses."
  }
  assert {
    condition     = google_identity_platform_config.this.client[0].permissions[0].disabled_user_deletion == true
    error_message = "Account deletion goes through the platform, not the browser."
  }
}
```

- [ ] **Step 2: See it fail**

Add the `terraform test` step to `.github/workflows/terraform.yml`: for each directory under `infra/terraform/modules/` that contains `tests/`, run `terraform init -backend=false -input=false && terraform test`. Push the branch.
Expected: the `terraform` check fails for `modules/identity` with "no configuration files".

- [ ] **Step 3: Write `modules/identity`**

One `google_project_service` for `identitytoolkit.googleapis.com` (`disable_on_destroy = false`) and one `google_identity_platform_config` named `this` that depends on it, with: `sign_in { allow_duplicate_emails = false; email { enabled = true; password_required = false } }`, `authorized_domains = concat(var.authorized_domains, ["${var.project_id}.firebaseapp.com"])` (the second is the domain that hosts the sign-in handler for Google sign-in; `localhost` is left out on purpose), `autodelete_anonymous_users = true`, `multi_tenant { allow_tenants = false }`, `client { permissions { disabled_user_signup = false; disabled_user_deletion = true } }`, `monitoring { request_logging { enabled = false } }`. Outputs as in Interfaces.

- [ ] **Step 4: Use it in both roots**

`envs/dev/members.tf`: `module "identity"` with `authorized_domains = ["dev.${var.domain}"]`. `envs/prod/members.tf`: `[var.domain, "www.${var.domain}"]`. Add the two root outputs. Extend `modules/web_service` with an `env` map input (default `{}`) if it has none, and give the `web` service of each root: `IDENTITY_API_KEY`, `IDENTITY_AUTH_DOMAIN`, `PLATFORM_API_URL` (the `platform-api` service's URL) and `SITE_ORIGIN` (`https://dev.${var.domain}` in dev, `https://${var.domain}` in prod). These names are the `web` settings of [contracts §6](../../contracts/stage-1-launch.md). Pass the key as `nonsensitive(module.identity.api_key)`: it is a public browser value, and a sensitive value inside the `env` map would make the whole map sensitive, which a `dynamic "env"` block refuses at plan time (`validate` does not catch this). Add the root output `web_url` (the `web` service's URL) if the root has none; contracts §7 lists it.

- [ ] **Step 5: See it pass**

Push. Expected: the `terraform` check passes: fmt, validate for both roots, 3 runs passed in `modules/identity`.

- [ ] **Step 6: Commit**

```bash
git add infra/terraform .github/workflows/terraform.yml
git commit -m "infra: Identity Platform with email-link sign-in, tested module"
```

---

### Task 2: The contact key

**Files:**
- Create: `infra/terraform/modules/contact_key/{main,variables,outputs}.tf`, `infra/terraform/modules/contact_key/tests/contact_key.tftest.hcl`
- Modify: `infra/terraform/envs/{dev,prod}/members.tf`, `infra/terraform/envs/{dev,prod}/identities.tf`

**Interfaces:**
- Produces: `module "contact_key"` with inputs `project_id`, `region`; outputs `key_id` (the crypto key's id) and `key_version_name` (`<key id>/cryptoKeyVersions/1`). Root output `contact_key_name` = `key_version_name`. `platform-api` receives it as `PLATFORM_CONTACT_KEY`.
- A custom project role `platformContactKeyUser` with exactly the permission `cloudkms.cryptoKeyVersions.useToSign`, bound on this key to the `platform-api` service account. Jobs that need it are bound in the slice that adds them.

- [ ] **Step 1: Write the failing test**

```hcl
# infra/terraform/modules/contact_key/tests/contact_key.tftest.hcl
mock_provider "google" {}

variables {
  project_id = "example-dev"
  region     = "asia-southeast1"
}

run "the_key_is_a_mac_key_that_never_rotates" {
  command = plan
  assert {
    condition     = google_kms_crypto_key.contact_id.purpose == "MAC"
    error_message = "contact_id is derived with a keyed hash."
  }
  assert {
    condition     = google_kms_crypto_key.contact_id.version_template[0].algorithm == "HMAC_SHA256"
    error_message = "Algorithm must be HMAC_SHA256."
  }
  assert {
    condition     = google_kms_crypto_key.contact_id.rotation_period == null
    error_message = "Rotation would change every contact id."
  }
  assert {
    condition     = google_kms_key_ring.platform.location == "asia-southeast1"
    error_message = "Key ring must be regional."
  }
}

run "the_version_name_points_at_version_one" {
  command = plan    # never apply: the clean-up after an apply would meet prevent_destroy
  override_resource {
    target          = google_kms_crypto_key.contact_id
    override_during = plan
    values          = { id = "projects/example-dev/locations/asia-southeast1/keyRings/platform/cryptoKeys/contact-id" }
  }
  assert {
    condition     = endswith(output.key_version_name, "/cryptoKeyVersions/1")
    error_message = "Callers sign with version 1."
  }
}
```

- [ ] **Step 2: See it fail**

Push. Expected: the check fails for `modules/contact_key` with "no configuration files".

- [ ] **Step 3: Write the module and use it**

`google_project_service` for `cloudkms.googleapis.com`; `google_kms_key_ring.platform` (name `platform`, `location = var.region`) and `google_kms_crypto_key.contact_id` (name `contact-id`, `purpose = "MAC"`, `version_template { algorithm = "HMAC_SHA256"; protection_level = "SOFTWARE" }`, no `rotation_period`, `lifecycle { prevent_destroy = true }`). In each root: the module, the custom role, one `google_kms_crypto_key_iam_member` for `platform-api` in `identities.tf`, the root output, and `PLATFORM_CONTACT_KEY` in the `platform-api` service's `env`.

- [ ] **Step 4: See it pass**

Push. Expected: the check passes; 2 runs passed in `modules/contact_key`.

- [ ] **Step 5: Commit**

```bash
git add infra/terraform
git commit -m "infra: contact key in Cloud KMS, usable only for signing by platform-api"
```

---

### Task 3: Three private buckets

**Files:**
- Create: `infra/terraform/modules/private_bucket/{main,variables,outputs}.tf`, `infra/terraform/modules/private_bucket/tests/private_bucket.tftest.hcl`
- Modify: `infra/terraform/envs/{dev,prod}/members.tf`, `identities.tf`, `variables.tf`; `ops/scripts/20-stage1-foundations.sh`; `docs/runbooks/` page for Gate 1

**Interfaces:**
- Produces: `module "private_bucket"` with inputs `name`, `project_id`, `location` (default `"ASIA-SOUTHEAST1"`), `versioning` (bool, default `false`), `delete_after_days` (number, default `null`), `force_destroy` (bool, default `false`); output `name`.
- Three instances per root and their outputs:

| Instance | Bucket name | Versioning | Deleted after | Readers | Writers |
| --- | --- | --- | --- | --- | --- |
| `library` | `<project_id>-library` | on | never | `platform-api` (object viewer) | `platform-api` (object creator: it copies published files in) |
| `library_staging` | `<project_id>-library-staging` | off | 7 days | `platform-api` | the owner |
| `roster_inbox` | `<project_id>-roster-inbox` | off | 7 days | none yet (the import job is bound in Wave 2) | the owner |

- New root variable `owner_member` (string, `sensitive = true`, no default): an IAM member such as `user:...`. This task adds one line to `ops/scripts/20-stage1-foundations.sh`, `export TF_VAR_owner_member="user:$(gcloud config get-value account)"` (the `user:` prefix is required), and the same line to the Gate 1 runbook before `terraform plan`. The value is never written to a file and the script does not print it.
- `platform-api` may sign download links without a key file: `roles/iam.serviceAccountTokenCreator` on **its own** service account, bound in `identities.tf`.
- `platform-api` receives `PLATFORM_LIBRARY_BUCKET`.

- [ ] **Step 1: Write the failing test**

```hcl
# infra/terraform/modules/private_bucket/tests/private_bucket.tftest.hcl
mock_provider "google" {}

variables {
  name       = "example-dev-library"
  project_id = "example-dev"
}

run "a_bucket_is_never_public" {
  command = plan
  assert {
    condition     = google_storage_bucket.this.public_access_prevention == "enforced"
    error_message = "Public access prevention must be enforced."
  }
  assert {
    condition     = google_storage_bucket.this.uniform_bucket_level_access == true
    error_message = "Uniform bucket-level access must be on."
  }
  assert {
    condition     = google_storage_bucket.this.location == "ASIA-SOUTHEAST1"
    error_message = "Buckets live in asia-southeast1."
  }
}

run "no_lifecycle_rule_unless_asked" {
  command = plan
  assert {
    condition     = length(google_storage_bucket.this.lifecycle_rule) == 0
    error_message = "The library keeps its files."
  }
}

run "delete_after_days_adds_exactly_one_delete_rule" {
  command = plan
  variables {
    delete_after_days = 7
  }
  assert {
    condition     = length(google_storage_bucket.this.lifecycle_rule) == 1
    error_message = "Expected one lifecycle rule."
  }
  assert {
    condition     = one(google_storage_bucket.this.lifecycle_rule[0].condition).age == 7
    error_message = "Objects are deleted after 7 days."
  }
  assert {
    condition     = one(google_storage_bucket.this.lifecycle_rule[0].action).type == "Delete"
    error_message = "The rule must delete."
  }
}

run "versioning_follows_the_input" {
  command = plan
  variables {
    versioning = true
  }
  assert {
    condition     = google_storage_bucket.this.versioning[0].enabled == true
    error_message = "Versioning must be on when asked."
  }
}
```

- [ ] **Step 2: See it fail**

Push. Expected: the check fails for `modules/private_bucket`.

- [ ] **Step 3: Write the module, the three instances, the bindings and the outputs**

`lifecycle_rule` is a `dynamic` block that appears only when `delete_after_days` is not null. `force_destroy` is `true` only for `library_staging` and `roster_inbox` in dev. The owner's bindings are `roles/storage.objectCreator` on the two inbox buckets, member `var.owner_member`.

- [ ] **Step 4: See it pass, and confirm no email reaches CI output**

Push. Expected: 4 runs passed. `terraform validate` in CI runs without `owner_member` (validate does not need variable values); confirm the workflow log contains no email-shaped string (search it for `[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[a-z]{2,}`; a plain `@` always matches, because the log prints `actions/checkout@v4`).

- [ ] **Step 5: Commit**

```bash
git add infra/terraform
git commit -m "infra: private buckets for the library, publish staging and the roster inbox"
```

---

### Task 4: DNS records for the sending domain

**Files:**
- Create: `infra/terraform/modules/sending_domain/{main,variables,outputs}.tf`, `infra/terraform/modules/sending_domain/tests/sending_domain.tftest.hcl`
- Modify: `infra/terraform/envs/{dev,prod}/members.tf`, `variables.tf`

**Interfaces:**
- Produces: `module "sending_domain"` with inputs `zone_id`, `zone_name` (the apex, for example `example.org`), `domain` (the sending domain: the apex or a subdomain of it), `project_id`, `spf_includes` (list of string, default `["_spf.firebasemail.com"]`), `dkim_targets` (map of selector to target host, default `null`, see Step 3), `dmarc_policy` (string, default `"none"`), `dmarc_report_address` (string, default `""`), `enabled` (bool). Output `domain`. Root output `auth_email_domain`.
- Records it creates when `enabled`:

| Type | Name | Value |
| --- | --- | --- |
| TXT | the sending domain | `v=spf1 include:<each of spf_includes> ~all`, **one record** |
| TXT | the sending domain | `firebase=<project_id>` |
| CNAME | `firebase1._domainkey.<sending domain>` | `dkim_targets["firebase1"]` |
| CNAME | `firebase2._domainkey.<sending domain>` | `dkim_targets["firebase2"]` |
| TXT | `_dmarc.<sending domain>` | `v=DMARC1; p=<dmarc_policy>` and, when the address is set, `; rua=mailto:<dmarc_report_address>` |

- In the roots: `enabled = var.manage_cloudflare_dns`, `zone_id = var.cloudflare_zone_id`.

- [ ] **Step 1: Write the failing test**

```hcl
# infra/terraform/modules/sending_domain/tests/sending_domain.tftest.hcl
mock_provider "cloudflare" {}

variables {
  enabled    = true
  zone_id    = "zone"
  zone_name  = "example.org"
  domain     = "dev.example.org"
  project_id = "example-dev"
}

run "exactly_one_spf_record_listing_every_include" {
  command = plan
  variables {
    spf_includes = ["_spf.firebasemail.com", "_spf.mx.cloudflare.net"]
  }
  assert {
    condition     = cloudflare_record.spf[0].content == "v=spf1 include:_spf.firebasemail.com include:_spf.mx.cloudflare.net ~all"
    error_message = "One SPF record must carry every include, in order."
  }
  assert {
    condition     = length(cloudflare_record.spf) == 1
    error_message = "A domain may have only one v=spf1 record."
  }
}

run "default_dkim_targets_follow_the_documented_pattern" {
  command = plan
  assert {
    condition     = cloudflare_record.dkim["firebase1"].content == "mail-dev-example-org.dkim1._domainkey.firebasemail.com"
    error_message = "Selector firebase1 must point at the dkim1 host for this domain."
  }
  assert {
    condition     = cloudflare_record.dkim["firebase2"].content == "mail-dev-example-org.dkim2._domainkey.firebasemail.com"
    error_message = "Selector firebase2 must point at the dkim2 host for this domain."
  }
  assert {
    condition     = cloudflare_record.dkim["firebase1"].proxied == false
    error_message = "Mail records are DNS-only."
  }
}

run "dmarc_starts_at_none_and_adds_reports_only_when_asked" {
  command = plan
  assert {
    condition     = cloudflare_record.dmarc[0].content == "v=DMARC1; p=none"
    error_message = "Default DMARC record."
  }
}

run "dmarc_with_a_report_address" {
  command = plan
  variables {
    dmarc_report_address = "reports@example.org"
  }
  assert {
    condition     = cloudflare_record.dmarc[0].content == "v=DMARC1; p=none; rua=mailto:reports@example.org"
    error_message = "DMARC record with a report address."
  }
}

run "disabled_creates_nothing" {
  command = plan
  variables {
    enabled = false
  }
  assert {
    condition     = length(cloudflare_record.spf) == 0 && length(cloudflare_record.dkim) == 0 && length(cloudflare_record.dmarc) == 0
    error_message = "No DNS records when DNS is not managed here."
  }
}
```

- [ ] **Step 2: See it fail**

Push. Expected: the check fails for `modules/sending_domain`.

- [ ] **Step 3: Write the module**

When `dkim_targets` is null, compute the two targets from the sending domain with every dot replaced by a dash: `mail-<dashed domain>.dkim1._domainkey.firebasemail.com` and `...dkim2...`. That pattern is what the service has shown for custom email domains; the list on the console's "customize domain" screen is the authority, and `dkim_targets` exists so the owner can override the computed values without a code change if her screen shows different ones. Record names are given relative to the zone: for the apex use `@`. Every record has `proxied = false` and `ttl = 300`.

- [ ] **Step 4: Use it in both roots**

Dev: `domain = "dev.${var.domain}"`. Prod: `domain = var.domain`. New root variables `auth_email_spf_includes` (default `["_spf.firebasemail.com"]`) and `auth_email_dkim_targets` (default `null`) pass through. A further root variable `signin_sender_hint` (string, default `""`) is given to the `web` service as `SIGNIN_SENDER_HINT`; the owner sets it once the first test email shows the exact sender address.

- [ ] **Step 5: See it pass**

Push. Expected: 5 runs passed in `modules/sending_domain`.

- [ ] **Step 6: Commit**

```bash
git add infra/terraform
git commit -m "infra: SPF, DKIM and DMARC records for the sign-in email's own domain"
```

---

### Task 5: Script that verifies and applies the sending domain

**Files:**
- Create: `ops/scripts/30-auth-email-domain.sh`, `ops/scripts/tests/stub-curl.sh`, `ops/scripts/tests/test-30.sh`
- Modify: `.github/workflows/terraform.yml` (run `shellcheck ops/scripts/*.sh ops/scripts/tests/*.sh` and `bash ops/scripts/tests/test-30.sh`)

**Interfaces:**
- `30-auth-email-domain.sh <project_id> <domain> [--dry-run]`. Safe to re-run. In order:
  1. Read the configuration: `GET https://identitytoolkit.googleapis.com/admin/v2/projects/<project_id>/config`, with `Authorization: Bearer $(gcloud auth print-access-token)` and the header `x-goog-user-project: <project_id>`.
  2. If `.notification.sendEmail.dnsInfo.customDomain` equals `<domain>` and `.notification.sendEmail.dnsInfo.useCustomDomain` is `true`: print `ALREADY APPLIED` and exit 0.
  3. If `.notification.sendEmail.dnsInfo.pendingCustomDomain` is not `<domain>`: `POST .../admin/v2/projects/<project_id>/domain:verify` with body `{"domain":"<domain>","action":"VERIFY"}`, then read the configuration again.
  4. Print `.notification.sendEmail.dnsInfo.customDomainState` and `domainVerificationRequestTime`.
  5. If the state says the domain is verified: `POST .../domain:verify` with `{"domain":"<domain>","action":"APPLY"}`, read the configuration again, and print `APPLIED` when `customDomain` equals `<domain>`. Otherwise print `NOT VERIFIED YET`, the four records to compare with the DNS zone, the command to re-run, and exit 3.
- `--dry-run` prints each request it would send (method, URL, body) and sends only the `GET`.
- `CURL` environment variable: the program used for HTTP, default `curl`. The tests set it to the stub.
- The script never prints the access token.

- [ ] **Step 1: Write the stub and the failing test**

Both scripts make every HTTP request through one helper with one shape, so that one stub serves both:

```bash
# status=$(call <METHOD> <URL> [<BODY>]); the response body is left in "$body_file"
call() { if [ $# -ge 3 ]; then printf '%s' "$3" | "$CURL" -sS -X "$1" -H "Authorization: Bearer $token" -H "x-goog-user-project: $project" -H 'content-type: application/json' -o "$body_file" -w '%{http_code}' --data @- "$2"; else "$CURL" -sS -X "$1" -H "Authorization: Bearer $token" -H "x-goog-user-project: $project" -o "$body_file" -w '%{http_code}' "$2"; fi; }
```

The body goes in on standard input, never as an argument (arguments show in the process list). `stub-curl.sh` honours exactly these options: it takes the method from `-X`, the output file from `-o`, the URL from the last argument, and reads the body from standard input when `--data @-` is present. It appends one line `<METHOD> <URL> <BODY>` to the file named by `$STUB_LOG`. For `GET` it copies the file named by `${STUB_RESPONSE:-}` to the `-o` file (an empty file when unset) and prints `${STUB_STATUS:-200}`; for `POST` and `PATCH` it writes `{}` to the `-o` file and prints `200`. `STUB_STATUS` therefore affects `GET` only.

```bash
# ops/scripts/tests/test-30.sh
#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../30-auth-email-domain.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
export CURL="$here/stub-curl.sh" STUB_LOG="$tmp/log" GCLOUD_TOKEN="stub-token"

run() { : > "$STUB_LOG"; STUB_RESPONSE="$tmp/config.json" bash "$script" example-dev dev.example.org "$@"; }
fail() { echo "FAIL: $1"; exit 1; }

# 1. Already applied: one GET, no POST, exit 0.
echo '{"notification":{"sendEmail":{"dnsInfo":{"customDomain":"dev.example.org","useCustomDomain":true}}}}' > "$tmp/config.json"
out="$(run)"; grep -q "ALREADY APPLIED" <<<"$out" || fail "should report already applied"
grep -q "^POST" "$STUB_LOG" && fail "must not POST when already applied"

# 2. Nothing requested yet: asks for verification, reports not verified, exit 3.
echo '{"notification":{"sendEmail":{"dnsInfo":{}}}}' > "$tmp/config.json"
set +e; out="$(run)"; code=$?; set -e
[ "$code" -eq 3 ] || fail "exit code should be 3 while unverified, got $code"
grep -q '"action":"VERIFY"' "$STUB_LOG" || fail "should request verification"
grep -q '"action":"APPLY"' "$STUB_LOG" && fail "must not apply an unverified domain"
grep -q "firebase1._domainkey.dev.example.org" <<<"$out" || fail "should list the records to check"

# 3. Dry run sends no POST.
out="$(run --dry-run || true)"
grep -q "^POST" "$STUB_LOG" && fail "dry run must not POST"

# 4. The token never appears in output.
grep -q "stub-token" <<<"$out" && fail "token leaked"
echo "test-30 passed"
```

- [ ] **Step 2: See it fail**

Run: `bash ops/scripts/tests/test-30.sh`
Expected: FAIL, the script does not exist.

- [ ] **Step 3: Write the script**

Conventions of `00-bootstrap.sh`: `set -euo pipefail`, a `say` helper, plain-language failures. The token comes from `${GCLOUD_TOKEN:-$(gcloud auth print-access-token)}`. Which value of `customDomainState` means "verified" is read from the API reference page for `Config` before coding and written as one named constant at the top of the script; treat any other value as not verified.

- [ ] **Step 4: See it pass**

Run: `bash ops/scripts/tests/test-30.sh && shellcheck ops/scripts/30-auth-email-domain.sh ops/scripts/tests/*.sh`
Expected: `test-30 passed`, no shellcheck output.

- [ ] **Step 5: Commit**

```bash
git add ops/scripts .github/workflows/terraform.yml
git commit -m "ops: script that verifies and applies the sign-in email's sending domain"
```

---

### Task 6: Script that stores the Google sign-in client, and the runbook

**Files:**
- Create: `ops/scripts/31-google-sign-in.sh`, `ops/scripts/tests/test-31.sh`, `docs/runbooks/stage-1-sign-in.md`
- Modify: `.github/workflows/terraform.yml` (run `test-31.sh`)

**Interfaces:**
- `31-google-sign-in.sh <project_id> [--dry-run]`. Prompts for the client id (`read -r`) and the client secret (`read -rs`, no echo). Then:
  1. `GET .../admin/v2/projects/<project_id>/defaultSupportedIdpConfigs/google.com`.
  2. If it does not exist (HTTP 404): `POST .../admin/v2/projects/<project_id>/defaultSupportedIdpConfigs?idpId=google.com` with `{"enabled":true,"clientId":"...","clientSecret":"..."}`.
  3. If it exists: `PATCH .../defaultSupportedIdpConfigs/google.com?updateMask=enabled,clientId,clientSecret` with the same body.
  4. Print `GOOGLE SIGN-IN ENABLED for <project_id>` and the client id's last six characters. Never print the secret.
- `--dry-run` prints the method and URL of each request with the body's secret replaced by `***`, and sends only the `GET`.
- `stub-curl.sh` is unchanged from Task 5: `STUB_STATUS=404` makes the `GET` answer 404 with an empty body; unset, it answers 200 with `$STUB_RESPONSE`.
- The script uses the same `call` helper as script 30 and reads the token the same way, `${GCLOUD_TOKEN:-$(gcloud auth print-access-token)}`, so the test never calls `gcloud`.

- [ ] **Step 1: Write the failing test**

```bash
# ops/scripts/tests/test-31.sh
#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../31-google-sign-in.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
export CURL="$here/stub-curl.sh" STUB_LOG="$tmp/log" GCLOUD_TOKEN="stub-token"
fail() { echo "FAIL: $1"; exit 1; }
answers=$'client-id-abcdef\nsecret-value-123\n'

# 1. Not configured yet: creates it.
: > "$STUB_LOG"; out="$(STUB_STATUS=404 bash "$script" example-dev <<<"$answers")"
grep -q "^POST .*defaultSupportedIdpConfigs?idpId=google.com" "$STUB_LOG" || fail "should create the provider"
grep -q "GOOGLE SIGN-IN ENABLED for example-dev" <<<"$out" || fail "should confirm"
grep -q "abcdef" <<<"$out" || fail "should show the end of the client id"

# 2. Already configured: updates it, does not create a second one.
echo '{"name":"projects/example-dev/defaultSupportedIdpConfigs/google.com","enabled":true}' > "$tmp/idp.json"
: > "$STUB_LOG"; out="$(STUB_RESPONSE="$tmp/idp.json" bash "$script" example-dev <<<"$answers")"
grep -q "^PATCH" "$STUB_LOG" || fail "should update"
grep -q "^POST" "$STUB_LOG" && fail "must not create twice"

# 3. The secret is never printed, in any mode.
grep -q "secret-value-123" <<<"$out" && fail "secret printed"
: > "$STUB_LOG"; out="$(STUB_STATUS=404 bash "$script" example-dev --dry-run <<<"$answers")"
grep -q "secret-value-123" <<<"$out" && fail "secret printed in dry run"
grep -q "^POST" "$STUB_LOG" && fail "dry run must not POST"
echo "test-31 passed"
```

- [ ] **Step 2: See it fail**

Run: `bash ops/scripts/tests/test-31.sh`
Expected: FAIL, the script does not exist.

- [ ] **Step 3: Write the script**

Send the body to `curl` on standard input (`--data @-`), never as an argument, so the secret does not appear in the process list.

- [ ] **Step 4: See it pass**

Run: `bash ops/scripts/tests/test-31.sh && shellcheck ops/scripts/31-google-sign-in.sh`
Expected: `test-31 passed`, no shellcheck output.

- [ ] **Step 5: Write `docs/runbooks/stage-1-sign-in.md`**

For the owner, every step a command unless stated, in this order, with what each prints when it worked:

1. **What this sets up and what it costs** (nothing while idle; Identity Platform is free at this size).
2. **Apply the infrastructure** with the foundations script; it now also creates the identity configuration, the key, the buckets and the DNS records.
3. **Start the sending domain's verification:** `bash ops/scripts/30-auth-email-domain.sh audhd-neurobiology-dev dev.audhdneurobiology.org`. Say that verification can take up to 24 hours, that exit code 3 means "not yet", and that the same command is run again later and then prints `APPLIED`. Then the same for prod with the apex domain.
4. **If it stays unverified:** the one place where a screen is needed. Firebase's documentation gives the path as: Firebase console → Security → Authentication → Templates → the edit icon of any template → "customize domain". (Opening the project in the Firebase console for the first time adds Firebase to it; say so.) Compare the records shown there with the zone and, if the DKIM targets differ, set `TF_VAR_auth_email_dkim_targets` and apply again. Write this step so that it still helps when the screen looks different: name what to look for (two CNAME records and two TXT records for the domain), not only where to click.
5. **Create the Google sign-in client** (console; there is no command for it): APIs & Services → Credentials → Create credentials → OAuth client ID → Web application; authorised redirect URI `https://<identity_auth_domain>/__/auth/handler`, taking the value from `terraform output identity_auth_domain`. Then `bash ops/scripts/31-google-sign-in.sh <project>` and paste the two values at the prompts.
6. **Check:** a sign-in email requested on the dev site arrives from the sending domain; in the received message's headers SPF, DKIM and DMARC all say `pass`. State where to look in Gmail ("Show original").
7. **Undo:** `domain:verify` with `CANCEL`; disable the provider.

- [ ] **Step 6: Commit and open the pull request**

```bash
git add ops/scripts docs/runbooks .github/workflows/terraform.yml
git commit -m "ops: Google sign-in client script and the sign-in runbook"
```

**Stop here.** Applying Terraform and running the scripts is the owner's step at Gate 1.

---

## Exit test for this plan

1. The `terraform` check passes on every pull request: fmt, validate for both roots, 14 test runs across four modules, both script tests, shellcheck.
2. After Gate 1 on dev: `terraform plan` is clean, and an anonymous `curl` of each bucket's URL returns 401 or 403.
3. `30-auth-email-domain.sh` prints `APPLIED` for dev within 24 hours of the DNS records existing.
4. A sign-in email requested on dev arrives from the sending domain and passes SPF, DKIM and DMARC.
