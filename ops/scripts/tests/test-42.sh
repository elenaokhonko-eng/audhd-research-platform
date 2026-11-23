#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../42-raise-test-alert.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"; cp "$here/stub-gcloud.sh" "$tmp/bin/gcloud"; chmod +x "$tmp/bin/gcloud"
export PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/log"
fail() { echo "FAIL: $1"; exit 1; }
run() { : > "$STUB_LOG"; set +e; out="$(bash "$script" "$@" 2>&1)"; code=$?; set -e; }
passed=0; ok() { passed=$((passed + 1)); }

# 1. A marker alert in dev: one entry in the test log carrying the marker.
run example-dev reconcile-failed
[ "$code" -eq 0 ] || fail "expected exit 0, got $code: $out"
grep -q "^logging write platform-test .*alert=reconcile_failed" "$STUB_LOG" || fail "should write the marker to platform-test: $(cat "$STUB_LOG")"
grep -q -- "--project example-dev" "$STUB_LOG" || fail "should name the project"
grep -q -- "--severity=ERROR" "$STUB_LOG" || fail "should write at severity ERROR"
grep -q "WROTE a test entry for reconcile-failed; the alert email should arrive within 5 minutes" <<<"$out" || fail "should confirm: $out"
ok

# 2. The address alert: an invented address outside the excluded domains.
run example-dev address-in-logs
[ "$code" -eq 0 ] || fail "address: expected exit 0, got $code: $out"
grep -q "^logging write platform-test .*@example.com" "$STUB_LOG" || fail "should write an @example.com address: $(cat "$STUB_LOG")"
ok

# 3. Production is refused before gcloud is called.
run example-prod reconcile-failed
[ "$code" -eq 2 ] || fail "prod: expected exit 2, got $code"
[ ! -s "$STUB_LOG" ] || fail "gcloud must not be called for prod: $(cat "$STUB_LOG")"
ok

# 4. An unknown alert name is refused.
run example-dev nonsense
[ "$code" -eq 2 ] || fail "unknown name: expected exit 2, got $code"
[ ! -s "$STUB_LOG" ] || fail "gcloud must not be called for an unknown name"
ok

run; [ "$code" -eq 2 ] || fail "no argument should exit 2"
run example-dev; [ "$code" -eq 2 ] || fail "one argument should exit 2"
echo "test-42: $passed passed"
