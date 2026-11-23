#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../40-stripe-key.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"; cp "$here/stub-gcloud.sh" "$tmp/bin/gcloud"; chmod +x "$tmp/bin/gcloud"
export PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/log" STUB_STDIN="$tmp/stdin"
fail() { echo "FAIL: $1"; exit 1; }
reset() { : > "$STUB_LOG"; : > "$STUB_STDIN"; }
run() { set +e; out="$(bash "$script" "$@" 2>&1)"; code=$?; set -e; }
passed=0; ok() { passed=$((passed + 1)); }

# 1. A restricted test key is stored through stdin; only its end is shown.
reset; printf 'rk_test_abcdefghijklmnop1234' | { run example-dev; [ "$code" -eq 0 ] || fail "good key: exit $code: $out"; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
out="$(cat "$tmp/out")"
grep -q "^secrets versions add stripe-read-key --project example-dev --data-file=-\$" "$STUB_LOG" || fail "stub not called as expected"
printf '%s' 'rk_test_abcdefghijklmnop1234' | cmp -s - "$STUB_STDIN" || fail "gcloud must receive exactly the key bytes (no newline added)"
grep -q "STORED a new version of stripe-read-key in example-dev" <<<"$out" || fail "should confirm"
grep -q "1234" <<<"$out" || fail "should show the last four"
grep -q "rk_test_abc" <<<"$out" && fail "key printed"
ok

# 2. A full secret key is refused, without repeating it.
reset; printf 'sk_test_abcdefghijklmnop1234' | { run example-dev; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
out="$(cat "$tmp/out")"; code="$(cat "$tmp/code")"
[ "$code" -eq 1 ] || fail "sk_ key: expected exit 1, got $code"
[ -s "$STUB_LOG" ] && fail "stub must not be called for sk_"
grep -q "full secret key" <<<"$out" || fail "should explain sk_"
grep -q "sk_test_abc" <<<"$out" && fail "sk_ key repeated"
ok

# 3. Live and test keys do not mix; --live needs the project id typed again.
reset; printf 'example-prod\nrk_test_abcdefghijklmnop1234' | { run example-prod --live; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
[ "$(cat "$tmp/code")" -eq 1 ] || fail "test key with --live should exit 1"
[ -s "$STUB_LOG" ] && fail "stub called for test key with --live"
reset; printf 'rk_live_abcdefghijklmnop1234' | { run example-dev; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
[ "$(cat "$tmp/code")" -eq 1 ] || fail "live key without --live should exit 1"
[ -s "$STUB_LOG" ] && fail "stub called for live key without --live"
reset; printf 'other-project\nrk_live_abcdefghijklmnop1234' | { run example-prod --live; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
[ "$(cat "$tmp/code")" -eq 1 ] || fail "mismatched project id should exit 1"
[ -s "$STUB_LOG" ] && fail "stub called after project mismatch"
reset; printf 'example-prod\nrk_live_abcdefghijklmnop1234' | { run example-prod --live; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
[ "$(cat "$tmp/code")" -eq 0 ] || fail "good live key should exit 0: $(cat "$tmp/out")"
grep -q -- "--project example-prod" "$STUB_LOG" || fail "live key not stored"
printf '%s' 'rk_live_abcdefghijklmnop1234' | cmp -s - "$STUB_STDIN" || fail "gcloud must receive exactly the live key bytes"
ok

# 4. Empty, short or odd values are refused.
for bad in '' 'rk_test_short' 'rk_test_abcdefghijklmnop12 34' 'rk_test_abcdefghijklmnop12-4'; do
  reset; printf '%s' "$bad" | { run example-dev; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
  [ "$(cat "$tmp/code")" -eq 1 ] || fail "value '$bad' should exit 1"
  [ -s "$STUB_LOG" ] && fail "stub called for '$bad'"
  [ -n "$bad" ] && grep -qF -- "$bad" "$tmp/out" && fail "refused value repeated"
done
ok

# 5. No argument: usage, exit 2.
run; [ "$code" -eq 2 ] || fail "no argument should exit 2, got $code"
grep -q "Usage:" <<<"$out" || fail "should print usage"
ok
run example-dev --live extra; [ "$code" -eq 2 ] || fail "a third argument should exit 2, got $code"

# 6. A live key belongs only in a -prod project, and a -prod project takes only a live key.
reset; printf 'example-dev\nrk_live_abcdefghijklmnop1234' | { run example-dev --live; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
[ "$(cat "$tmp/code")" -eq 1 ] || fail "--live for a dev project should exit 1"
[ -s "$STUB_LOG" ] && fail "stub called for --live in a dev project"
grep -q "real customers" "$tmp/out" || fail "should explain why a live key stays out of dev"
grep -q "rk_live_abc" "$tmp/out" && fail "live key repeated"
reset; printf 'rk_test_abcdefghijklmnop1234' | { run example-prod; echo "$out" > "$tmp/out"; echo "$code" > "$tmp/code"; }
[ "$(cat "$tmp/code")" -eq 1 ] || fail "a -prod project without --live should exit 1"
[ -s "$STUB_LOG" ] && fail "stub called for a test key in a -prod project"
grep -q "invented people" "$tmp/out" || fail "should explain why prod takes only a live key"
ok

echo "test-40: $passed passed"
