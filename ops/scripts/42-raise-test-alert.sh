#!/usr/bin/env bash
# Raises one of the platform's log-based alerts in dev, to check that its email reaches the owner.
#   bash ops/scripts/42-raise-test-alert.sh <project_id> <name>
# <name> is one of: reconcile-failed, reconcile-guard-blocked, roster-refused, roster-truncated, address-in-logs.
# It writes one entry to the log "platform-test". `gcloud logging write` cannot set a Cloud Run resource,
# so the alert filters accept that log by name, and only in dev (module platform_alerts, accept_test_log).
# Exit codes: 0 the entry was written, 1 the write failed, 2 wrong usage, a production project or an unknown name.
# Safe to run twice: each run writes one more entry and raises the alert again.
set -euo pipefail

usage() {
  echo "Usage: bash ops/scripts/42-raise-test-alert.sh <project_id> <name>" >&2
  echo "  <name>: reconcile-failed | reconcile-guard-blocked | roster-refused | roster-truncated | address-in-logs" >&2
  exit 2
}

project="${1:-}"
name="${2:-}"
[[ -n "$project" && -n "$name" ]] || usage

if [[ "$project" == *-prod ]]; then
  echo "Refused: $project is a production project. Test alerts are raised in dev only." >&2
  exit 2
fi

case "$name" in
  reconcile-failed | reconcile-guard-blocked | roster-refused | roster-truncated)
    # The marker the code writes: the alert's name with underscores.
    text="Test entry from 42-raise-test-alert.sh: alert=${name//-/_}" ;;
  address-in-logs)
    # An invented address outside the two excluded domains (example.org, gserviceaccount.com).
    text="Test entry from 42-raise-test-alert.sh: contact someone@example.com" ;;
  *)
    echo "Refused: unknown alert name '$name'." >&2
    usage ;;
esac

gcloud logging write platform-test "$text" --project "$project" --severity=ERROR
echo "WROTE a test entry for $name; the alert email should arrive within 5 minutes"
