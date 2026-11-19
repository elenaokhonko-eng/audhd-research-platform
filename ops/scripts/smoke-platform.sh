#!/usr/bin/env bash
# Smoke test of the Stage 1 platform in one project. Run in Cloud Shell from the repository root:
#   bash ops/scripts/smoke-platform.sh audhd-neurobiology-dev
# It needs the real platform-api image deployed (20-stage1-foundations.sh step 6, or CI).
# Prints SMOKE PASSED, or the first step that failed and exits non-zero. It never prints a token.
#
#   a. platform-api /health with your identity token        -> "mode":"api"
#   b. platform-hooks /health without a token                -> "mode":"hooks"; /v1/ping -> 404
#   c. run the job platform-selfcheck; read the event id from its last log line
#   d. wait up to 60 s for Firestore document inbox/<event id> (Pub/Sub delivered it)
#   e. publish the same event again; platform-api must log it as a duplicate and run no handler
set -euo pipefail

export PATH="$HOME/bin:$PATH"
PROJECT="${1:-}"
REGION="${REGION:-asia-southeast1}"
# How platform-api words its log line for a repeated event, and for a handler that runs.
DUPLICATE_PATTERN="${SMOKE_DUPLICATE_PATTERN:-duplicate}"
HANDLER_PATTERN="${SMOKE_HANDLER_PATTERN:-handler}"

if [[ -z "$PROJECT" ]]; then
  echo "Usage: bash ops/scripts/smoke-platform.sh <project id>, e.g. audhd-neurobiology-dev" >&2
  exit 2
fi

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
fail() { # fail step reason
  printf '\n\033[1;31mSMOKE FAILED at step %s: %s\033[0m\n' "$1" "$2" >&2
  exit 1
}

service_url() { # service_url name
  gcloud run services describe "$1" --region="$REGION" --project="$PROJECT" --format='value(status.url)'
}

# curl with a bearer token passed through a file descriptor, so it never appears in the
# process list or on screen. Prints the body, then the HTTP status on the last line.
curl_bearer() { # curl_bearer token url
  curl -sS --max-time 30 -w '\n%{http_code}' \
    -H @<(printf 'Authorization: Bearer %s\n' "$1") "$2"
}
# The same for Google APIs, billed to the project under test.
curl_google_api() { # curl_google_api token url
  curl -sS --max-time 30 -w '\n%{http_code}' \
    -H @<(printf 'Authorization: Bearer %s\nx-goog-user-project: %s\n' "$1" "$PROJECT") "$2"
}
curl_plain() { # curl_plain url
  curl -sS --max-time 30 -w '\n%{http_code}' "$1"
}

# ---------------------------------------------------------------- a
say "a. platform-api /health (private, with your identity token)"
API_URL="$(service_url platform-api)" || fail a "cannot read the URL of platform-api in ${PROJECT}"
[[ -n "$API_URL" ]] || fail a "platform-api does not exist in ${PROJECT}"
ID_TOKEN="$(gcloud auth print-identity-token)" || fail a "gcloud could not issue an identity token"
OUT="$(curl_bearer "$ID_TOKEN" "${API_URL}/health")" || fail a "platform-api did not answer"
unset ID_TOKEN
CODE="$(tail -n1 <<<"$OUT")"; BODY="$(sed '$d' <<<"$OUT")"
[[ "$CODE" == "200" ]] || fail a "platform-api /health answered HTTP ${CODE} (403 means your account may not invoke it)"
grep -Eq '"mode": ?"api"' <<<"$BODY" || fail a "platform-api /health did not say \"mode\":\"api\" (is the placeholder image still deployed?): ${BODY}"
echo "ok: ${BODY}"

# ---------------------------------------------------------------- b
say "b. platform-hooks /health and /v1/ping (public, no token)"
HOOKS_URL="$(service_url platform-hooks)" || fail b "cannot read the URL of platform-hooks in ${PROJECT}"
[[ -n "$HOOKS_URL" ]] || fail b "platform-hooks does not exist in ${PROJECT}"
OUT="$(curl_plain "${HOOKS_URL}/health")" || fail b "platform-hooks did not answer"
CODE="$(tail -n1 <<<"$OUT")"; BODY="$(sed '$d' <<<"$OUT")"
[[ "$CODE" == "200" ]] || fail b "platform-hooks /health answered HTTP ${CODE}"
grep -Eq '"mode": ?"hooks"' <<<"$BODY" || fail b "platform-hooks /health did not say \"mode\":\"hooks\": ${BODY}"
echo "ok: ${BODY}"
OUT="$(curl_plain "${HOOKS_URL}/v1/ping")" || fail b "platform-hooks did not answer /v1/ping"
CODE="$(tail -n1 <<<"$OUT")"
[[ "$CODE" == "404" ]] || fail b "platform-hooks /v1/ping answered HTTP ${CODE}; the API routes must not exist in hooks mode"
echo "ok: /v1/ping is 404"

# ---------------------------------------------------------------- c
say "c. Job platform-selfcheck"
EXECUTION="$(gcloud run jobs execute platform-selfcheck --region="$REGION" --project="$PROJECT" \
  --wait --format='value(metadata.name)')" || fail c "the job platform-selfcheck failed or could not start"
[[ -n "$EXECUTION" ]] || fail c "the job ran but gcloud did not return its execution name"
echo "execution: ${EXECUTION}"
EVENT_ID=""
for _ in $(seq 1 12); do   # logs can take a few seconds to arrive
  EVENT_ID="$(gcloud logging read \
    "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"platform-selfcheck\" AND labels.\"run.googleapis.com/execution_name\"=\"${EXECUTION}\"" \
    --project="$PROJECT" --order=desc --limit=20 --format='value(textPayload,jsonPayload.message)' \
    | tr -d '[:blank:]' | grep -Em1 '^[0-9A-Fa-f-]{32,36}$' || true)"
  [[ -n "$EVENT_ID" ]] && break
  sleep 5
done
[[ -n "$EVENT_ID" ]] || fail c "no event id in the logs of execution ${EXECUTION} after 60 s"
echo "event id: ${EVENT_ID}"

# ---------------------------------------------------------------- d
say "d. Firestore inbox/${EVENT_ID}"
DOC_URL="https://firestore.googleapis.com/v1/projects/${PROJECT}/databases/(default)/documents/inbox/${EVENT_ID}"
FOUND=""
for _ in $(seq 1 12); do
  ACCESS_TOKEN="$(gcloud auth print-access-token)" || fail d "gcloud could not issue an access token"
  CODE="$(curl_google_api "$ACCESS_TOKEN" "$DOC_URL" | tail -n1)" || CODE="000"
  unset ACCESS_TOKEN
  if [[ "$CODE" == "200" ]]; then FOUND=yes; break; fi
  [[ "$CODE" == "403" ]] && fail d "Firestore refused to let your account read inbox/${EVENT_ID} (HTTP 403)"
  sleep 5
done
[[ -n "$FOUND" ]] || fail d "inbox/${EVENT_ID} did not appear within 60 s: the push from Pub/Sub to platform-api did not succeed. Look at: gcloud run services logs read platform-api --region ${REGION} --project ${PROJECT} --limit 50"
echo "ok: the event was delivered and recorded"

# ---------------------------------------------------------------- e
say "e. Publish the same event again"
SINCE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
NOW="$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)"
EVENT_TYPE="org.audhdneurobiology.platform.selfcheck.ran"
MESSAGE="$(printf '{"specversion":"1.0","id":"%s","type":"%s","source":"//audhdneurobiology.org/platform-api","subject":"platform-api","time":"%s","datacontenttype":"application/json","data":{"check":"bus"}}' \
  "$EVENT_ID" "$EVENT_TYPE" "$NOW")"
gcloud pubsub topics publish platform.events --project="$PROJECT" --message="$MESSAGE" \
  --attribute="ce-id=${EVENT_ID},ce-type=${EVENT_TYPE},ce-subject=platform-api" >/dev/null \
  || fail e "could not publish to platform.events"
LINES=""
for _ in $(seq 1 18); do
  LINES="$(gcloud logging read \
    "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"platform-api\" AND timestamp>=\"${SINCE}\" AND \"${EVENT_ID}\"" \
    --project="$PROJECT" --order=asc --limit=50 --format='value(textPayload,jsonPayload.message)' || true)"
  grep -qi -- "$DUPLICATE_PATTERN" <<<"$LINES" && break
  sleep 5
done
grep -qi -- "$DUPLICATE_PATTERN" <<<"$LINES" \
  || fail e "within 90 s platform-api logged no line containing '${DUPLICATE_PATTERN}' for ${EVENT_ID}"
if grep -i -- "$HANDLER_PATTERN" <<<"$LINES" | grep -vi -e "$DUPLICATE_PATTERN" -e 'no handler' | grep -q .; then
  fail e "a handler ran for the repeated event ${EVENT_ID}; it should have been skipped as a duplicate"
fi
echo "ok: the second delivery was acknowledged as a duplicate and no handler ran"

printf '\n\033[1;32mSMOKE PASSED\033[0m (%s)\n' "$PROJECT"
