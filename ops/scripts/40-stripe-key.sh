#!/usr/bin/env bash
# Stores the restricted Stripe key (read-only) as a new version of the secret stripe-read-key.
# Run in Google Cloud Shell from the repository root, after Terraform has created the secret:
#   bash ops/scripts/40-stripe-key.sh <project_id> [--live]
# The key is typed or pasted without echo (or read from standard input when it is not a terminal),
# is passed to gcloud on standard input (never as an argument, so it is not in the process list)
# and is never printed: only its last four characters are shown afterwards.
# Without --live it accepts only a test key (rk_test_). With --live it accepts only a live key (rk_live_)
# and first asks you to type the project id again.
# Safe to re-run: each run adds a new version; older versions stay until you disable them.
# Exit codes: 0 stored, 1 refused or failed, 2 wrong usage.
set -euo pipefail
set +x # tracing would print the key

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
stop() { printf '\n\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

project="${1:-}"; live=0
if [[ -z "$project" || $# -gt 2 ]]; then
  echo "Usage: bash ops/scripts/40-stripe-key.sh <project_id> [--live]" >&2
  exit 2
fi
case "${2:-}" in
  "") ;;
  --live) live=1 ;;
  *) echo "Unknown option ${2}. The only option is --live." >&2; exit 2 ;;
esac

# ask <prompt> <hidden 0|1>: reads one line into $answer, from the terminal or from standard input.
ask() {
  answer=""
  if [[ -t 0 ]]; then
    if [[ "$2" -eq 1 ]]; then read -rs -p "$1" answer || true; echo >&2
    else read -r -p "$1" answer || true; fi
  else
    read -r answer || true
  fi
  answer="${answer%$'\r'}"
}

if [[ "$live" -eq 1 ]]; then
  say "LIVE key for $project"
  ask "This stores a key for real money. Type the project id again to continue: " 0
  [[ "$answer" == "$project" ]] || stop "The project id typed does not match $project. Nothing was stored. Re-run and type it exactly."
  prefix="rk_live_"
else
  say "Test key for $project"
  prefix="rk_test_"
fi

ask "Restricted Stripe key (starts $prefix; typed without echo): " 1
key="$answer"; answer=""

[[ -n "$key" ]] || stop "No key was entered. Nothing was stored. Re-run and paste the restricted key."
if [[ "$key" == sk_* ]]; then
  key=""
  stop "That value starts with sk_. It is a full secret key, which can move money, and must never be stored here. Nothing was stored. In Stripe, create a restricted key (it starts rk_) with read access only, then re-run."
fi
if [[ "$key" != "$prefix"* ]]; then
  key=""
  if [[ "$live" -eq 1 ]]; then
    stop "With --live the key must start $prefix. Nothing was stored. If this is a test key, re-run without --live."
  fi
  stop "The key must start $prefix. Nothing was stored. If this is a live key, re-run with --live."
fi
if [[ ${#key} -lt 20 ]]; then key=""; stop "The key is shorter than 20 characters, so it was probably cut off when pasting. Nothing was stored. Re-run and paste it again."; fi
if [[ ! "$key" =~ ^[A-Za-z0-9_]+$ ]]; then key=""; stop "The key holds characters other than letters, digits and underscore, so it was probably pasted with extra text. Nothing was stored. Re-run and paste only the key."; fi

say "Adding a new version of stripe-read-key in $project"
if ! printf '%s' "$key" | gcloud secrets versions add stripe-read-key --project "$project" --data-file=-  >/dev/null; then
  key=""
  stop "gcloud could not add the version. Nothing is known to have been stored. Check that Terraform has created the secret in $project and that you have the Secret Manager Admin or Secret Version Adder role, then re-run."
fi
last4="${key: -4}"
key=""; unset key

echo "STORED a new version of stripe-read-key in $project"
echo "The key ends in: $last4"
