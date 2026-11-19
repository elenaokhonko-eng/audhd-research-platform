#!/usr/bin/env bash
# Stores the Google sign-in client (OAuth client id and secret) in Identity Platform.
# Run in Google Cloud Shell from the repository root, after creating the client in the console
# (docs/runbooks/stage-1-sign-in.md, step 5):
#   bash ops/scripts/31-google-sign-in.sh <project_id> [--dry-run]
# It asks for the client id and the client secret. The secret is typed without echo, is sent to Google
# on standard input (never as an argument, so it is not in the process list) and is never printed.
# Safe to re-run: it creates the Google provider when missing and updates it when present.
# --dry-run prints each change it would send (method, URL, body with the secret as ***) and sends only the read.
# Exit codes: 0 done, 1 failure, 2 wrong usage.
# This script never prints the access token or the secret.
set -euo pipefail

CURL="${CURL:-curl}"
API="https://identitytoolkit.googleapis.com/admin/v2/projects"

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
stop() { printf '\n\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

project="${1:-}"; dry=0
if [[ -z "$project" ]]; then
  echo "Usage: bash ops/scripts/31-google-sign-in.sh <project_id> [--dry-run]" >&2
  exit 2
fi
case "${2:-}" in
  "") ;;
  --dry-run) dry=1 ;;
  *) echo "Unknown option ${2}. The only option is --dry-run." >&2; exit 2 ;;
esac
command -v jq >/dev/null || stop "jq is not installed (Cloud Shell has it). Install it, then re-run."

token="${GCLOUD_TOKEN:-$(gcloud auth print-access-token 2>/dev/null)}" || stop "Could not get an access token from gcloud. Run 'gcloud auth login', then re-run."
[[ -n "$token" ]] || stop "Could not get an access token from gcloud. Run 'gcloud auth login', then re-run."
body_file="$(mktemp)"; trap 'rm -f "$body_file"' EXIT

# status=$(call <METHOD> <URL> [<BODY>]); the response body is left in "$body_file"
call() { if [ $# -ge 3 ]; then printf '%s' "$3" | "$CURL" -sS -X "$1" -H "Authorization: Bearer $token" -H "x-goog-user-project: $project" -H 'content-type: application/json' -o "$body_file" -w '%{http_code}' --data @- "$2"; else "$CURL" -sS -X "$1" -H "Authorization: Bearer $token" -H "x-goog-user-project: $project" -o "$body_file" -w '%{http_code}' "$2"; fi; }

say "Google sign-in client for $project"
read -r -p "Client id (ends in .apps.googleusercontent.com): " client_id \
  || stop "The input ended before a client id was entered. Nothing was changed. Re-run in a terminal and paste the client id."
read -rs -p "Client secret (typed without echo): " client_secret \
  || stop "The input ended before a client secret was entered. Nothing was changed. Re-run in a terminal and paste the client secret."
echo
[[ -n "$client_id" ]] || stop "No client id was entered. Nothing was changed. Re-run and paste the client id."
[[ -n "$client_secret" ]] || stop "No client secret was entered. Nothing was changed. Re-run and paste the client secret."

# The values travel in the environment of jq, not in its arguments.
make_body() { CID="$client_id" SEC="$1" jq -cn '{enabled:true,clientId:env.CID,clientSecret:env.SEC}'; }
body="$(make_body "$client_secret")"
shown_body="$(make_body '***')"

idp_url="$API/$project/defaultSupportedIdpConfigs"

say "1/2 Reading the current Google provider of $project"
status="$(call GET "$idp_url/google.com")" || stop "Could not reach Google (the request itself failed). Check your connection and re-run."
case "$status" in
  200) method="PATCH"; url="$idp_url/google.com?updateMask=enabled,clientId,clientSecret" ;;
  404) method="POST"; url="$idp_url?idpId=google.com" ;;
  *) stop "Google answered HTTP $status when reading the sign-in providers of $project. If it is 403, your account needs the role 'Firebase Authentication Admin' on the project and the Identity Toolkit API must be on (Terraform enables it). If it is 400 or 404 on every try, check the project id. Then re-run." ;;
esac

say "2/2 Saving the Google provider"
if [[ "$dry" -eq 1 ]]; then
  echo "DRY RUN, would send: $method $url $shown_body"
  echo "Dry run: nothing was changed."
  exit 0
fi
status="$(call "$method" "$url" "$body")" || stop "Could not reach Google while saving the provider. Re-run; it is safe to repeat."
[[ "$status" == "200" ]] || stop "Google answered HTTP $status when saving the Google provider of $project. Nothing is known to have changed. Check the client id and secret in the console, then re-run."

echo "GOOGLE SIGN-IN ENABLED for $project"
echo "Client id ends in: ${client_id: -6}"
