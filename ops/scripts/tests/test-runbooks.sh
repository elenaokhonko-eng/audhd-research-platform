#!/usr/bin/env bash
# Checks the owner's launch and operations runbooks (docs/runbooks/launch.md, operations.md):
# both exist; every ops/scripts/NN-*.sh they name exists; every platform-cli command they name
# is one of the contract's (docs/contracts/stage-1-launch.md section 6 and its refinements);
# and neither holds an address outside example.org, a Stripe key prefix (rk_live_, sk_) or a
# 12-digit number (the shape of a project number).
# The checks are first run against invented bad pages, so a check that stops catching fails too.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(cd "$here/../../.." && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

# The platform-cli commands of contracts section 6 and the refinements below its module table.
# `job <name>` takes any job name.
allowed_commands=(
  "runs show" "campaign apply" "promo apply" "launch set" "launch report"
  "contact show" "grant create" "grant revoke" "support list" "library publish"
  "member delete" "member deletions"
)

problems=()
problem() { problems+=("$1"); }

# check_page <file> <repository root>: adds one line to problems per finding.
check_page() {
  local page="$1" repo="$2" name script cmd first second known allowed
  name="$(basename "$page")"

  while IFS= read -r script; do
    [[ -n "$script" ]] || continue
    [[ -f "$repo/$script" ]] || problem "$name names $script, which does not exist"
  done < <(grep -oE 'ops/scripts/[0-9]{2}-[A-Za-z0-9._-]+\.sh' "$page" | sort -u || true)

  while IFS= read -r cmd; do
    [[ -n "$cmd" ]] || continue
    read -r _ first second <<<"$cmd"
    known=0
    if [[ "$first" == "job" ]]; then
      known=1
    else
      for allowed in "${allowed_commands[@]}"; do
        [[ "$first ${second:-}" == "$allowed" ]] && known=1
      done
    fi
    [[ "$known" -eq 1 ]] || problem "$name names '$cmd', which is not a command of the contract"
  done < <(grep -oE 'platform-cli( [a-z][a-z-]*){1,2}' "$page" | sort -u || true)

  while IFS= read -r address; do
    [[ -n "$address" ]] || continue
    [[ "$address" == *@example.org ]] || problem "$name holds an address outside example.org"
  done < <(grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$page" || true)

  if grep -qE '(^|[^A-Za-z0-9_])(rk_live_|sk_)' "$page"; then
    problem "$name holds a string starting rk_live_ or sk_"
  fi
  if grep -qE '(^|[^0-9])[0-9]{12}([^0-9]|$)' "$page"; then
    problem "$name holds a 12-digit number"
  fi
}

fail() { echo "FAIL: $1"; exit 1; }
passed=0; ok() { passed=$((passed + 1)); }

# expect_caught <description> <page text>: the check must find something in this page.
expect_caught() {
  problems=()
  printf '%s\n' "$2" > "$tmp/page.md"
  check_page "$tmp/page.md" "$root"
  [[ "${#problems[@]}" -gt 0 ]] || fail "the check missed $1"
  ok
}

# 1. Each check catches what it is for, and lets a clean page through.
expect_caught "a script that does not exist" 'bash ops/scripts/99-no-such-script.sh example-dev'
expect_caught "a command outside the contract" 'platform-cli member purge --all'
expect_caught "a command word with no subcommand" 'Then platform-cli prints the list.'
expect_caught "an address outside example.org" 'Write to someone@example.com'
expect_caught "a live restricted key prefix" 'the key rk_live_abc'
expect_caught "a secret key prefix" 'never paste sk_test_abc'
expect_caught "a 12-digit number" 'project number 123456789012'
problems=()
printf '%s\n' 'bash ops/scripts/40-stripe-key.sh example-dev' 'platform-cli job stripe-reconcile' \
  'platform-cli runs show --kind stripe_reconcile' 'printf %s you@example.org | platform-cli contact show --email-stdin' \
  'a task_count of 1; 2026-11-23' > "$tmp/clean.md"
check_page "$tmp/clean.md" "$root"
[[ "${#problems[@]}" -eq 0 ]] || fail "a clean page was refused: ${problems[*]}"
ok

# 2. The two runbooks.
problems=()
for page in launch.md operations.md; do
  if [[ ! -f "$root/docs/runbooks/$page" ]]; then
    problem "docs/runbooks/$page does not exist"
    continue
  fi
  check_page "$root/docs/runbooks/$page" "$root"
done
if [[ "${#problems[@]}" -gt 0 ]]; then
  printf '  %s\n' "${problems[@]}"
  fail "${#problems[@]} problem(s) in the runbooks"
fi
ok

echo "test-runbooks: $passed checks passed"
