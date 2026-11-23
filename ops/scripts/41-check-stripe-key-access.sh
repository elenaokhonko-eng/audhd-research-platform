#!/usr/bin/env bash
# Checks who can read the Stripe key. Read-only: it changes nothing and prints no key and no address of a person.
#   bash ops/scripts/41-check-stripe-key-access.sh <project_id>
# Exit codes: 0 only the reconcile job (job-stripe) is granted on the secret, 1 anything else or a failed read, 2 wrong usage.
# It also prints, as information, how many members hold project-level roles that can read every secret,
# because the secret's own policy is not the whole answer.
set -euo pipefail

stop() { printf '\n\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

project="${1:-}"
if [[ -z "$project" ]]; then
  echo "Usage: bash ops/scripts/41-check-stripe-key-access.sh <project_id>" >&2
  exit 2
fi
command -v jq >/dev/null || stop "jq is not installed (Cloud Shell has it). Install it, then re-run."

expected="serviceAccount:job-stripe@${project}.iam.gserviceaccount.com"
accessor="roles/secretmanager.secretAccessor"

policy="$(gcloud secrets get-iam-policy stripe-read-key --project "$project" --format=json)" \
  || stop "Could not read the policy of the secret stripe-read-key in $project. Check the project id and that Terraform has created the secret."

# One line per role on the secret: "<role> <member count>".
roles="$(jq -r '(.bindings // [])[] | select((.members // []) | length > 0) | "\(.role) \(.members | length)"' <<<"$policy")"
accessors="$(jq -r --arg a "$accessor" '(.bindings // [])[] | select(.role == $a) | (.members // [])[]' <<<"$policy" | sort)"
other_roles="$(jq -r --arg a "$accessor" '(.bindings // [])[] | select(.role != $a and ((.members // []) | length > 0)) | .role' <<<"$policy")"

echo "Secret stripe-read-key in $project, roles with members:"
if [[ -n "$roles" ]]; then sed 's/^/  /; s/ \([0-9][0-9]*\)$/: \1 member(s)/' <<<"$roles"; else echo "  none"; fi

# The project's own policy: information only; the secret's policy decides the exit code.
if pol="$(gcloud projects get-iam-policy "$project" --format=json 2>/dev/null)" && jq -e . >/dev/null 2>&1 <<<"$pol"; then
  echo "At project level, these roles can also read every secret (information, not a failure):"
  for r in roles/owner roles/secretmanager.admin "$accessor"; do
    n="$(jq -r --arg r "$r" '[(.bindings // [])[] | select(.role == $r) | (.members // [])[]] | length' <<<"$pol")"
    echo "  $r: $n member(s)"
  done
else
  echo "Could not read the project's policy; the project-level roles were not checked."
fi

if [[ "$accessors" == "$expected" && -z "$other_roles" ]]; then
  echo "ONLY job-stripe IS GRANTED ON THE SECRET"
  exit 0
fi
echo "ACCESS IS WIDER THAN job-stripe ALONE. Compare the list above with what Terraform declares (infra/terraform/modules), then fix it there." >&2
exit 1
