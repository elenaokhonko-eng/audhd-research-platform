# Stage 1 sign-in runbook: sending domain and Google sign-in

Everything below runs in **Google Cloud Shell**, from the repository root, after the foundations runbook ([stage-1-foundations.md](stage-1-foundations.md)). Do dev first, then prod. Every script can be run again safely: it reads the current setting first.

Two terms. **Identity Platform** is Google's sign-in service; members get a sign-in link by email or sign in with Google. A **sending domain** is the domain those emails come from; its DNS records (SPF, DKIM, DMARC) tell receiving mail servers that the mail is genuine.

## 1. What this sets up and what it costs

It sets up the sign-in configuration, the contact key, the storage buckets, the DNS records for the sending domain, and the Google sign-in client. **It costs nothing while idle.** Identity Platform is free at this size, buckets and the key cost cents at most while empty.

Your own sign-in address is stored in the private Terraform state (as a member of the bucket grants), never in the repository. Do not put it in any file you commit.

## 2. Apply the infrastructure

Run the foundations script as described in the foundations runbook. It now also creates the identity configuration, the key, the buckets and the DNS records.

Before you apply **prod**, check whether the apex already has an SPF record:

```bash
dig +short TXT audhdneurobiology.org
```

A domain may carry **only one** `v=spf1` record. If the answer contains one that Terraform does not manage, delete it in Cloudflare and add its `include:` hosts to Terraform's list, for example:

```bash
export TF_VAR_auth_email_spf_includes='["_spf.firebasemail.com","<other include host>"]'
```

Then apply. It worked when Terraform ends with `Apply complete!` and a plan run straight afterwards says no changes.

## 3. Start the sending domain's verification

Dev uses `auth.dev.audhdneurobiology.org`, not `dev.`: `dev` is a CNAME to the site, and DNS does not allow a TXT record beside a CNAME.

```bash
bash ops/scripts/30-auth-email-domain.sh audhd-neurobiology-dev auth.dev.audhdneurobiology.org
```

Verification can take up to 24 hours. What the exit codes mean:

| Code | Meaning | What to do |
| --- | --- | --- |
| 0 | Done: prints `APPLIED` (or `ALREADY APPLIED`) | Nothing |
| 3 | Not verified yet | Wait, then run the same command again. It prints the records it expects |
| 1 | Failed (Google refused, the state is `FAILED`, or the request did not go through) | Read the message. If the records do not match, fix them; if Google does not offer domain verification to the project, do step 4 |

Then prod, with the apex domain:

```bash
bash ops/scripts/30-auth-email-domain.sh audhd-neurobiology-prod audhdneurobiology.org
```

## 4. If it stays unverified (or the script says Google does not offer it)

This is the one place where a screen is needed. Firebase's documentation gives the path as: Firebase console, Security, Authentication, Templates, the edit icon of any template, "customize domain". Opening the project in the Firebase console for the first time adds Firebase to it; that is expected and free.

If the screen looks different, look for this: it lists the domain and **two CNAME records and two TXT records** to add to DNS. Compare them with the zone in Cloudflare (`terraform output auth_email_domain`). If the DKIM (CNAME) targets differ from ours, set them and apply again:

```bash
export TF_VAR_auth_email_dkim_targets='{"firebase1":"<first target>","firebase2":"<second target>"}'
```

It is a map from the record's selector (`firebase1`, `firebase2`) to the host it points to. Then press the verify button in the console and re-run step 3's command; it should print `APPLIED`.

## 5. Create the Google sign-in client

There is no command for this part; use the console. APIs & Services, Credentials, Create credentials, OAuth client ID, Web application.

- **Authorised redirect URI:** `https://<identity_auth_domain>/__/auth/handler`. Get the value with:
  ```bash
  terraform -chdir=infra/terraform/envs/dev output -raw identity_auth_domain
  ```
  (the same with `envs/prod` for prod).
- **Authorised JavaScript origins:** the origin of the site, for example `https://dev.audhdneurobiology.org` for dev.

Then store the client:

```bash
bash ops/scripts/31-google-sign-in.sh audhd-neurobiology-dev
```

Paste the client id, then the secret (nothing shows as you type). It worked when it prints `GOOGLE SIGN-IN ENABLED for audhd-neurobiology-dev` and the last six characters of the client id. The secret is never printed, never written to a file and never enters Terraform state. Use `--dry-run` first if you want to see what it would send.

## 6. Check

Request a sign-in email on the dev site, using an address of yours (for example `you@example.org` stands for it here). It should arrive from the sending domain. In Gmail open the message, the three dots, **Show original**: SPF, DKIM and DMARC must all say `PASS`.

Once the first test email shows the sender address, set it and apply again so the site can show it to members:

```bash
export TF_VAR_signin_sender_hint='<the sender address shown>'
```

## 7. Undo

Stop using the custom sending domain, then turn the provider off:

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
