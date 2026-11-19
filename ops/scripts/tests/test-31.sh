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
