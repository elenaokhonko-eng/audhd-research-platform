#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
script="$here/../41-check-stripe-key-access.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"; cp "$here/stub-gcloud.sh" "$tmp/bin/gcloud"; chmod +x "$tmp/bin/gcloud"
export PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/log"
export STUB_POLICY="$tmp/policy.json" STUB_PROJECT_POLICY="$tmp/project.json"
fail() { echo "FAIL: $1"; exit 1; }
run() { set +e; out="$(bash "$script" "$@" 2>&1)"; code=$?; set -e; }
passed=0; ok() { passed=$((passed + 1)); }
job='serviceAccount:job-stripe@example-dev.iam.gserviceaccount.com'
cat > "$STUB_PROJECT_POLICY" <<JSON
{"bindings":[{"role":"roles/owner","members":["user:owner@example.org"]},
 {"role":"roles/secretmanager.admin","members":["user:a@example.org","user:b@example.org"]}]}
JSON

# 1. Exactly the one expected member.
printf '{"bindings":[{"role":"roles/secretmanager.secretAccessor","members":["%s"]}]}' "$job" > "$STUB_POLICY"
run example-dev
[ "$code" -eq 0 ] || fail "expected exit 0, got $code: $out"
grep -q "ONLY job-stripe IS GRANTED ON THE SECRET" <<<"$out" || fail "should confirm"
grep -q "roles/secretmanager.admin" <<<"$out" || fail "should print the project-level information"
grep -q "@example.org" <<<"$out" && fail "address printed"
ok

# 2. A second accessor.
printf '{"bindings":[{"role":"roles/secretmanager.secretAccessor","members":["%s","user:person@example.org"]}]}' "$job" > "$STUB_POLICY"
run example-dev
[ "$code" -eq 1 ] || fail "second accessor: expected exit 1, got $code"
grep -q "@example.org" <<<"$out" && fail "address of a person printed"
grep -q "ONLY job-stripe" <<<"$out" && fail "must not confirm"
ok

# 3. An extra role on the secret.
printf '{"bindings":[{"role":"roles/secretmanager.secretAccessor","members":["%s"]},{"role":"roles/secretmanager.admin","members":["group:team@example.org"]}]}' "$job" > "$STUB_POLICY"
run example-dev
[ "$code" -eq 1 ] || fail "extra role: expected exit 1, got $code"
grep -q "roles/secretmanager.admin" <<<"$out" || fail "should name the extra role"
grep -q "@example.org" <<<"$out" && fail "address printed"
ok
run; [ "$code" -eq 2 ] || fail "no argument should exit 2"
echo "test-41: $passed passed"
