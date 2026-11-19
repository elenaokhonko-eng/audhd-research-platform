#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../30-auth-email-domain.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
export CURL="$here/stub-curl.sh" STUB_LOG="$tmp/log" GCLOUD_TOKEN="stub-token"

run() { : > "$STUB_LOG"; STUB_RESPONSE="$tmp/config.json" bash "$script" example-dev dev.example.org "$@"; }
fail() { echo "FAIL: $1"; exit 1; }

# 1. Already applied: one GET, no POST, exit 0.
echo '{"notification":{"sendEmail":{"dnsInfo":{"customDomain":"dev.example.org","useCustomDomain":true}}}}' > "$tmp/config.json"
out="$(run)"; grep -q "ALREADY APPLIED" <<<"$out" || fail "should report already applied"
grep -q "^POST" "$STUB_LOG" && fail "must not POST when already applied"

# 2. Nothing requested yet: asks for verification, reports not verified, exit 3.
echo '{"notification":{"sendEmail":{"dnsInfo":{}}}}' > "$tmp/config.json"
set +e; out="$(run)"; code=$?; set -e
[ "$code" -eq 3 ] || fail "exit code should be 3 while unverified, got $code"
grep -q '"action":"VERIFY"' "$STUB_LOG" || fail "should request verification"
grep -q '"action":"APPLY"' "$STUB_LOG" && fail "must not apply an unverified domain"
grep -q "firebase1._domainkey.dev.example.org" <<<"$out" || fail "should list the records to check"

# 3. Dry run sends no POST.
out="$(run --dry-run || true)"
grep -q "^POST" "$STUB_LOG" && fail "dry run must not POST"

# 4. The token never appears in output.
grep -q "stub-token" <<<"$out" && fail "token leaked"
echo "test-30 passed"
