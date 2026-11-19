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
# 4. Reading the provider is refused (403): stops, changes nothing, prints no secret.
: > "$STUB_LOG"; set +e; out="$(STUB_STATUS=403 bash "$script" example-dev <<<"$answers" 2>&1)"; code=$?; set -e
[ "$code" -ne 0 ] || fail "403 on read should stop with a non-zero exit"
grep -qE "^(POST|PATCH)" "$STUB_LOG" && fail "must not write after a refused read"
grep -q "secret-value-123" <<<"$out" && fail "secret printed after 403"
# 5. Input ends before the client id: stops with a message, sends nothing.
: > "$STUB_LOG"; set +e; out="$(bash "$script" example-dev </dev/null 2>&1)"; code=$?; set -e
[ "$code" -eq 1 ] || fail "end of input should stop with exit 1, got $code"
grep -q "Nothing was changed" <<<"$out" || fail "end of input should say nothing was changed"
[ -s "$STUB_LOG" ] && fail "must not call Google after end of input"
echo "test-31 passed"
