#!/usr/bin/env bash
# Verifies and applies the sending domain of the sign-in emails (Identity Platform).
# Run in Google Cloud Shell from the repository root, after Terraform has created the DNS records:
#   bash ops/scripts/30-auth-email-domain.sh <project_id> <domain> [--dry-run]
# Dev example:
#   bash ops/scripts/30-auth-email-domain.sh audhd-neurobiology-dev auth.dev.audhdneurobiology.org
# Safe to re-run: it reads the current setting first and changes nothing when it already matches.
# --dry-run prints each change it would send (method, URL, body) and sends only the read.
# Exit codes: 0 applied (or already), 1 failure, 2 wrong usage, 3 DNS not verified yet.
# This script never prints the access token.
set -euo pipefail

# Value of Config.notification.sendEmail.dnsInfo.customDomainState that means "verified".
# Identity Toolkit API v2 discovery document, DnsInfo.customDomainState (VerificationState): the values
# are VERIFICATION_STATE_UNSPECIFIED, NOT_STARTED, IN_PROGRESS, FAILED and SUCCEEDED. SUCCEEDED means
# "verified and ready to be applied". Anything else counts as not verified.
VERIFIED_STATE="SUCCEEDED"

CURL="${CURL:-curl}"
API="https://identitytoolkit.googleapis.com/admin/v2/projects"

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
stop() { printf '\n\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

project="${1:-}"; domain="${2:-}"; dry=0
if [[ -z "$project" || -z "$domain" ]]; then
  echo "Usage: bash ops/scripts/30-auth-email-domain.sh <project_id> <domain> [--dry-run]" >&2
  exit 2
fi
case "${3:-}" in
  "") ;;
  --dry-run) dry=1 ;;
  *) echo "Unknown option ${3}. The only option is --dry-run." >&2; exit 2 ;;
esac
command -v jq >/dev/null || stop "jq is not installed (Cloud Shell has it). Install it, then re-run."

token="${GCLOUD_TOKEN:-$(gcloud auth print-access-token 2>/dev/null)}" || stop "Could not get an access token from gcloud. Run 'gcloud auth login', then re-run."
[[ -n "$token" ]] || stop "Could not get an access token from gcloud. Run 'gcloud auth login', then re-run."
body_file="$(mktemp)"; trap 'rm -f "$body_file"' EXIT

# status=$(call <METHOD> <URL> [<BODY>]); the response body is left in "$body_file"
call() { if [ $# -ge 3 ]; then printf '%s' "$3" | "$CURL" -sS -X "$1" -H "Authorization: Bearer $token" -H "x-goog-user-project: $project" -H 'content-type: application/json' -o "$body_file" -w '%{http_code}' --data @- "$2"; else "$CURL" -sS -X "$1" -H "Authorization: Bearer $token" -H "x-goog-user-project: $project" -o "$body_file" -w '%{http_code}' "$2"; fi; }

config_url="$API/$project/config"
verify_url="$API/$project/domain:verify"

read_config() {
  local status
  status="$(call GET "$config_url")" || stop "Could not reach Google (the request itself failed). Check your connection and re-run."
  if [[ "$status" != "200" ]]; then
    stop "Google answered $status when reading the sign-in settings of $project. If it is 403, your account needs the role 'Firebase Authentication Admin' on the project and the Identity Toolkit API must be on (Terraform enables it). If it is 404, check the project id. Then re-run. If it keeps failing, use the console instead: Firebase console > Authentication > Templates > edit any template > 'customize domain', following docs/runbooks/stage-1-sign-in.md."
  fi
  config="$(cat "$body_file")"
}
field() { jq -r ".notification.sendEmail.dnsInfo.$1 // empty" <<<"$config"; }

post_verify() { # post_verify VERIFY|APPLY
  local body status
  body="{\"domain\":\"$domain\",\"action\":\"$1\"}"
  if [[ "$dry" -eq 1 ]]; then
    echo "DRY RUN, would send: POST $verify_url $body"
    return 0
  fi
  status="$(call POST "$verify_url" "$body")" || stop "Could not reach Google while sending the $1 request. Re-run."
  if [[ "$status" != "200" ]]; then
    stop "Google answered HTTP $status to the $1 request for $domain. Google may not offer this method to your project (it is not in the published API description), so this script cannot always do the step. Do it in the console instead: Firebase console > Authentication > Templates > edit any template > 'customize domain', following docs/runbooks/stage-1-sign-in.md. Then re-run this script to check the result."
  fi
}

say "1/3 Reading the current sign-in email settings of $project"
read_config
if [[ "$(field customDomain)" == "$domain" && "$(field useCustomDomain)" == "true" ]]; then
  echo "ALREADY APPLIED: sign-in emails already use $domain."
  exit 0
fi

say "2/3 Verification of $domain"
if [[ "$(field pendingCustomDomain)" != "$domain" ]]; then
  post_verify VERIFY
  read_config
fi
state="$(field customDomainState)"
echo "State: ${state:-none yet}"
echo "Verification requested at: $(field domainVerificationRequestTime || true)"

if [[ "$state" != "$VERIFIED_STATE" ]]; then
  say "NOT VERIFIED YET"
  if [[ "$state" == "FAILED" ]]; then
    echo "Google checked and verification FAILED: the DNS records it found do not match. Do not just wait; compare the records below with the zone and correct them."
  fi
  cat <<RECORDS
Google has not confirmed the DNS records of $domain yet. DNS changes can take from a few minutes
up to a few hours. Compare these with what Terraform created (terraform output auth_email_domain,
and the DNS zone in Cloudflare):
  TXT    $domain                          v=spf1 include:_spf.firebasemail.com ~all
  TXT    $domain                          firebase=$project
  CNAME  firebase1._domainkey.$domain     (value shown by Terraform)
  CNAME  firebase2._domainkey.$domain     (value shown by Terraform)
Also present, not needed for verification: TXT _dmarc.$domain
The domain may carry only one v=spf1 record; if the zone shows two, merge them.
When they match, wait a little and run again:
  bash ops/scripts/30-auth-email-domain.sh $project $domain
RECORDS
  exit 3
fi

say "3/3 Applying $domain"
post_verify APPLY
if [[ "$dry" -eq 1 ]]; then
  echo "Dry run: nothing was changed."
  exit 0
fi
read_config
if [[ "$(field customDomain)" == "$domain" ]]; then
  echo "APPLIED: sign-in emails now come from $domain."
else
  stop "The apply request was accepted but the settings do not show $domain yet. Re-run this script in a minute; it is safe to repeat."
fi
