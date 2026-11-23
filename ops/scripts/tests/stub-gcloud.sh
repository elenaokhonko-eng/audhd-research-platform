#!/usr/bin/env bash
# Stand-in for gcloud in tests (test-40, test-41). Tests put a copy named "gcloud" first on PATH.
# It records its arguments in $STUB_LOG and, for "versions add", its standard input in $STUB_STDIN.
# It answers "secrets get-iam-policy" from the file $STUB_POLICY and "projects get-iam-policy" from $STUB_PROJECT_POLICY.
echo "$*" >> "${STUB_LOG:-/dev/null}"
case "$*" in
  *"versions add"*) cat >> "${STUB_STDIN:-/dev/null}" ;;
  *"secrets get-iam-policy"*) cat "${STUB_POLICY:?STUB_POLICY is not set}" ;;
  *"projects get-iam-policy"*) cat "${STUB_PROJECT_POLICY:?STUB_PROJECT_POLICY is not set}" ;;
  *) echo "stub gcloud: unexpected call: $*" >&2; exit 64 ;;
esac
