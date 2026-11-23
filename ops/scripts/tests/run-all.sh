#!/usr/bin/env bash
# Runs every test-*.sh in this folder, in name order, and fails if any of them fails.
set -uo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
failed=0
for t in "$here"/test-*.sh; do
  if bash "$t"; then echo "PASS $(basename "$t")"; else echo "FAIL $(basename "$t")"; failed=$((failed + 1)); fi
done
[ "$failed" -eq 0 ] || { echo "$failed test file(s) failed"; exit 1; }
echo "all test files passed"
