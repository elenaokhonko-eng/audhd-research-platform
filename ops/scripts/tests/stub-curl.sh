#!/usr/bin/env bash
# Stand-in for curl in script tests. Honours only: -X METHOD, -o FILE, --data @-, last argument = URL.
# Logs "<METHOD> <URL> <BODY>" to $STUB_LOG. GET copies ${STUB_RESPONSE:-} to the -o file and prints
# ${STUB_STATUS:-200}; POST and PATCH write {} and print 200.
set -euo pipefail
method="GET"; out=""; has_body=0; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -X) method="$2"; shift 2 ;;
    -o) out="$2"; shift 2 ;;
    --data) [ "$2" = "@-" ] && has_body=1; shift 2 ;;
    -H|-w) shift 2 ;;
    *) url="$1"; shift ;;
  esac
done
body=""
if [ "$has_body" -eq 1 ]; then body="$(cat)"; fi
printf '%s %s %s\n' "$method" "$url" "$body" >> "$STUB_LOG"
if [ "$method" = "GET" ]; then
  if [ -n "${STUB_RESPONSE:-}" ]; then cp "$STUB_RESPONSE" "$out"; else : > "$out"; fi
  printf '%s' "${STUB_STATUS:-200}"
else
  printf '{}' > "$out"
  printf '200'
fi
