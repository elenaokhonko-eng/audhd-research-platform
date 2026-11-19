# Stage 1 sign-in runbook: sending domain and Google sign-in

Everything below runs in **Google Cloud Shell**, from the repository root, alongside the foundations runbook ([stage-1-foundations.md](stage-1-foundations.md)). Do "Before you run anything" first, then the foundations script, then dev, then prod. Every script can be run again safely: it reads the current setting first.

Two terms. **Identity Platform** is Google's sign-in service; members get a sign-in link by email or sign in with Google. A **sending domain** is the domain those emails come from; its DNS records (SPF, DKIM, DMARC) tell receiving mail servers that the mail is genuine. Prod sends from `audhdneurobiology.org`; dev sends from `auth.dev.audhdneurobiology.org` (not `dev.`: `dev` is a CNAME to the site, and DNS does not allow a TXT record beside a CNAME).

## Before you run anything: records the domain already has

A domain may carry **only one** SPF record (`v=spf1 ...`) and one DMARC record (`v=DMARC1 ...`). A second one breaks mail authentication for every sender of the domain. Terraform writes one of each for the sending domain, so first look at what is already there:

```bash
dig +short TXT audhdneurobiology.org
dig +short TXT _dmarc.audhdneurobiology.org
dig +short TXT auth.dev.audhdneurobiology.org
dig +short TXT _dmarc.auth.dev.audhdneurobiology.org
```

- The two `auth.dev` lines should print nothing. If they print a `v=spf1` or `v=DMARC1` record, treat it as below, with `envs/dev`, the state bucket `audhd-neurobiology-dev-tfstate` and the `auth.dev` names in place of `envs/prod`, `audhd-neurobiology-prod-tfstate` and the apex.
- Other TXT records on the apex (for example `google-site-verification=...`) are fine; only `v=spf1` and `v=DMARC1` matter.
- If the apex has **no** `v=spf1` and **no** `v=DMARC1` record, skip to section 1.

If the apex has a `v=spf1` or `v=DMARC1` record that Terraform does not manage yet, **import** it: Terraform then takes over the existing record and changes its content, instead of adding a second record beside it. Do this **before** the foundations script applies prod.

**a. Set up the shell.** Terraform needs your account and the Cloudflare token. Nothing is shown while you paste the token, and it is not saved anywhere:

```bash
export TF_VAR_owner_member="user:$(gcloud config get-value account)"
read -rs -p "Cloudflare API token: " TF_VAR_cloudflare_api_token; echo; export TF_VAR_cloudflare_api_token
ZONE="$(grep -E '^cloudflare_zone_id' infra/terraform/envs/prod/terraform.tfvars | cut -d'"' -f2)"
terraform -chdir=infra/terraform/envs/prod init -input=false -backend-config="bucket=audhd-neurobiology-prod-tfstate"
```

**b. Find the record ids** (each DNS record in Cloudflare has an id). With the Cloudflare API:

```bash
curl -sS -H "Authorization: Bearer $TF_VAR_cloudflare_api_token" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?type=TXT&name=audhdneurobiology.org" \
  | jq -r '.result[] | select(.content | test("v=spf1")) | "\(.id)  \(.content)"'
curl -sS -H "Authorization: Bearer $TF_VAR_cloudflare_api_token" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE/dns_records?type=TXT&name=_dmarc.audhdneurobiology.org" \
  | jq -r '.result[] | select(.content | test("v=DMARC1")) | "\(.id)  \(.content)"'
```

Each line is the record id, then its content. Without the API: Cloudflare dashboard, the zone, DNS, Records, Edit on the record; the id is at the end of the page address, or under "Record ID" in the record's details.

**c. Import them:**

```bash
terraform -chdir=infra/terraform/envs/prod import 'module.sending_domain.cloudflare_record.spf[0]' "$ZONE/<spf record id>"
terraform -chdir=infra/terraform/envs/prod import 'module.sending_domain.cloudflare_record.dmarc[0]' "$ZONE/<dmarc record id>"
```

**d. Keep its senders.** Before the next plan, put every `include:` host of the old SPF record into Terraform's list, so that the plan only rewrites the content and no other sender loses its permission. Settings like this one go into the git-ignored file `infra/terraform/envs/<env>/terraform.tfvars`, which Terraform reads on every run (an exported variable would be forgotten by a new Cloud Shell tab). Check the file is ignored (the command prints the path) and that the setting is not there yet (it prints nothing):

```bash
git check-ignore infra/terraform/envs/prod/terraform.tfvars
grep -nE '^(auth_email_spf_includes|auth_email_dkim_targets|signin_sender_hint)' infra/terraform/envs/prod/terraform.tfvars
```

Then append it, with `_spf.firebasemail.com` first and each old include host after it:

```bash
cat >> infra/terraform/envs/prod/terraform.tfvars <<'EOF'
auth_email_spf_includes = ["_spf.firebasemail.com", "<include host of the old record>"]
EOF
```

A setting may appear only once in the file: if the `grep` printed it, edit that line instead of appending (`nano infra/terraform/envs/prod/terraform.tfvars`).

Two things to know:

- **Cloudflare Email Routing** (if you forward mail with it) adds its own SPF record and locks it. If Email Routing is on, keep its include (`_spf.mx.cloudflare.net`) in the list. If Cloudflare refuses Terraform's change because the record is locked, Email Routing's settings page lists the records it locked and lets you unlock them.
- The record always ends in **`~all`** ("mail from anyone else is suspect", not rejected). An old record ending in `-all` becomes `~all`.

If the old DMARC record has a stricter policy than `p=none` or a `rua=` report address, the plan will show Terraform loosening it to `v=DMARC1; p=none`. Answer anything but `yes` at that prompt and ask for a DMARC setting to be added to Terraform first.

If the foundations script already applied prod before you did this, the apex now has two `v=spf1` records. Fold the old record's includes into `auth_email_spf_includes` as in step d, apply again, then delete the old record in Cloudflare (the one **without** the comment "Sign-in email SPF (Terraform)"). Do the same for a second `v=DMARC1` record on `_dmarc`.

## 1. What this sets up and what it costs

It sets up the sign-in configuration, the contact key, the storage buckets, the DNS records for the sending domain, and the Google sign-in client. **It costs nothing while idle.** Identity Platform is free at this size, buckets and the key cost cents at most while empty.

Your own sign-in address is stored in the private Terraform state (as a member of the bucket grants), never in the repository. Do not put it in any file you commit.

## 2. Apply the infrastructure

Run the foundations script as described in the foundations runbook. It also creates the identity configuration, the key, the buckets and the DNS records:

```bash
bash ops/scripts/20-stage1-foundations.sh
```

The script is safe to re-run: finished steps are skipped. It applies **both** roots, prod first and then dev, shows each plan and asks you to type `yes` before changing anything (it also asks again whether to move the prod project into the folder; answer as before). It sets `TF_VAR_owner_member` itself and asks for the Cloudflare token if it is not set. The mail settings (`auth_email_spf_includes`, `auth_email_dkim_targets`, `signin_sender_hint`) come from each root's `terraform.tfvars`, so they hold in any shell. Read the plan: it should show only the change you expect.

It worked when Terraform ends with `Apply complete!` and a plan run straight afterwards says no changes.

## 3. Start the sending domain's verification

```bash
bash ops/scripts/30-auth-email-domain.sh audhd-neurobiology-dev auth.dev.audhdneurobiology.org
```

Verification can take up to 24 hours. What the exit codes mean:

| Code | Meaning | What to do |
| --- | --- | --- |
| 0 | Done: prints `APPLIED` (or `ALREADY APPLIED`). With `--dry-run`: verified, and it printed the APPLY request it would send | Nothing |
| 3 | Not verified yet: the state is not `SUCCEEDED`. If it is `FAILED` (or `NOT_STARTED`), the script has just asked Google to check again | Compare the records it prints with the zone in Cloudflare, fix any that differ, wait, then run the same command again. If it keeps saying `FAILED`, do step 4 |
| 1 | Failed: Google refused a request, the request did not go through, or the apply was accepted but the settings do not show the domain in use yet | Read the message. After an apply, re-run in a minute. If Google does not offer domain verification to the project, do step 4 |
| 2 | Wrong usage: a missing argument or an unknown option | Run it as shown above |

Then prod, with the apex domain:

```bash
bash ops/scripts/30-auth-email-domain.sh audhd-neurobiology-prod audhdneurobiology.org
```

## 4. If it stays unverified (or the script says Google does not offer it)

This is the one place where a screen is needed. Firebase's documentation gives the path as: Firebase console, Security, Authentication, Templates, the edit icon of any template, "customize domain". Opening the project in the Firebase console for the first time adds Firebase to it; that is expected and free.

If the screen looks different, look for this: it lists the domain and **two CNAME records and two TXT records** to add to DNS. Compare them with the zone in Cloudflare (`terraform -chdir=infra/terraform/envs/dev output auth_email_domain`, and `envs/prod` for prod). If the DKIM (CNAME) targets differ from ours, write them into the root's git-ignored `terraform.tfvars` (shown for dev; for prod use `envs/prod`). Check first that the setting is not there yet, as in "Before you run anything", step d; if it is, edit that line instead:

```bash
cat >> infra/terraform/envs/dev/terraform.tfvars <<'EOF'
auth_email_dkim_targets = { firebase1 = "<first target>", firebase2 = "<second target>" }
EOF
```

It is a map from the record's selector (`firebase1`, `firebase2`) to the host it points to. Apply again:

```bash
bash ops/scripts/20-stage1-foundations.sh
```

The notes in step 2 apply (both roots, plan shown, you type `yes`).

Then press the verify button in the console and re-run step 3's command; it should print `APPLIED`.

## 5. Create the Google sign-in client

There is no command for this part; use the console, in the project you are setting up (dev first, then prod).

**a. The OAuth consent screen** (the page Google shows a member before they sign in). APIs & Services, OAuth consent screen (newer consoles call it Google Auth Platform, with the pages Branding, Audience and Data access):

- **User type:** External.
- **App name:** AuDHD Neurobiology (dev: AuDHD Neurobiology dev).
- **User support email and developer contact:** type them in the console. They are never written to a file.
- **Authorised domains:** `audhdneurobiology.org` and `firebaseapp.com`.
- **Scopes:** `openid`, `email` and `profile` only. These need no review by Google.
- Then **Publish app**, so the status moves from Testing to **In production**. In Testing mode only the test users you list can sign in.

**b. The client.** APIs & Services, Credentials, Create credentials, OAuth client ID, Web application.

- **Authorised redirect URI:** `https://<identity_auth_domain>/__/auth/handler`. Get the value with:
  ```bash
  terraform -chdir=infra/terraform/envs/dev output -raw identity_auth_domain
  ```
  For prod: `terraform -chdir=infra/terraform/envs/prod output -raw identity_auth_domain`.
- **Authorised JavaScript origins:** dev: `https://dev.audhdneurobiology.org`; prod: `https://audhdneurobiology.org` and `https://www.audhdneurobiology.org`.

Then store the client:

```bash
bash ops/scripts/31-google-sign-in.sh audhd-neurobiology-dev
```

For prod, make its own consent screen and client (its own redirect URI) and run:

```bash
bash ops/scripts/31-google-sign-in.sh audhd-neurobiology-prod
```

Paste the client id, then the secret (nothing shows as you type). It worked when it prints `GOOGLE SIGN-IN ENABLED for audhd-neurobiology-dev` and the last six characters of the client id. The secret is never printed, never written to a file and never enters Terraform state. Use `--dry-run` first if you want to see what it would send.

## 6. Check

**The buckets are private.** Asked without credentials, each must answer `401` or `403` (shown for dev; for prod use `audhd-neurobiology-prod`):

```bash
for b in library library-staging roster-inbox; do
  curl -s -o /dev/null -w '%{http_code}\n' "https://storage.googleapis.com/audhd-neurobiology-dev-$b/"
done
```

Any `200` means a bucket can be listed by anyone: stop and report it.

**The sign-in email.** Request a sign-in email on the dev site, using an address of yours (for example `you@example.org` stands for it here). It should arrive from the sending domain. In Gmail open the message, the three dots, **Show original**: SPF, DKIM and DMARC must all say `PASS`.

Once the first test email shows the sender address, write it into the root's git-ignored `terraform.tfvars` so the site can show it to members (shown for dev; for prod use `envs/prod`, after prod's own test email). Check first that the setting is not there yet, as in "Before you run anything", step d:

```bash
cat >> infra/terraform/envs/dev/terraform.tfvars <<'EOF'
signin_sender_hint = "<the sender address shown>"
EOF
```

Then apply again:

```bash
bash ops/scripts/20-stage1-foundations.sh
```

The notes in step 2 apply (both roots, plan shown, you type `yes`).

## 7. Undo

Stop using the custom sending domain, then turn the provider off. Shown for dev; for prod use project `audhd-neurobiology-prod` and the domain `audhdneurobiology.org` in both commands.

```bash
TOKEN="$(gcloud auth print-access-token)"
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "x-goog-user-project: audhd-neurobiology-dev" \
  -H 'content-type: application/json' \
  -d '{"domain":"auth.dev.audhdneurobiology.org","action":"CANCEL"}' \
  https://identitytoolkit.googleapis.com/admin/v2/projects/audhd-neurobiology-dev/domain:verify
curl -sS -X PATCH -H "Authorization: Bearer $TOKEN" -H "x-goog-user-project: audhd-neurobiology-dev" \
  -H 'content-type: application/json' -d '{"enabled":false}' \
  "https://identitytoolkit.googleapis.com/admin/v2/projects/audhd-neurobiology-dev/defaultSupportedIdpConfigs/google.com?updateMask=enabled"
```

If Google refuses the CANCEL request, undo it in the console instead: the same screen as step 4 (Firebase console, Authentication, Templates, edit icon, "customize domain").
