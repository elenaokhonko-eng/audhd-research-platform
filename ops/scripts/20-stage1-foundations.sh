#!/usr/bin/env bash
# Stage 1 foundations. Run in Google Cloud Shell from the repository root, after Stage 0:
#   bash ops/scripts/20-stage1-foundations.sh
# Safe to re-run: every step checks before it creates. Runbook: docs/runbooks/stage-1-foundations.md
#
# What it does
#   1. creates the folder audhd-neurobiology under the organisation and, after you answer y,
#      moves the prod project into it
#   2. creates the dev project in that folder and links it to the prod project's billing account
#   3. creates the dev Terraform state bucket
#   4. Terraform in envs/prod: removes web-dev and dev.<domain> from prod, adds the platform
#   5. Terraform in envs/dev: creates the dev project's services and takes over dev.<domain>
#   6. builds the website and deploys it to web-dev in the dev project; builds the first
#      platform-api image and deploys it to both projects (when the service exists)
#   7. creates the GitHub environments dev and production and sets their variables
#   8. reminds you to make yourself the required reviewer of production
# This script never prints a secret or your email address.
set -euo pipefail

export PATH="$HOME/bin:$PATH"   # Terraform installed by 00-bootstrap.sh
PROD_PROJECT="${PROD_PROJECT:-audhd-neurobiology-prod}"
DEV_PROJECT="${DEV_PROJECT:-audhd-neurobiology-dev}"
FOLDER_NAME="${FOLDER_NAME:-audhd-neurobiology}"
REGION="${REGION:-asia-southeast1}"
GITHUB_REPO="${GITHUB_REPO:-elenaokhonko-eng/audhd-research-platform}"
DOMAIN="${DOMAIN:-audhdneurobiology.org}"
ROOT="$(git rev-parse --show-toplevel)"
PROD_DIR="$ROOT/infra/terraform/envs/prod"
DEV_DIR="$ROOT/infra/terraform/envs/dev"

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
stop() { printf '\n\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

# tfvar_line file name: print the "name = value" line of a terraform.tfvars, or nothing
tfvar_line() { grep -E "^$2[[:space:]]*=" "$1" 2>/dev/null | tail -1 || true; }

# Explains the failures met in Stage 0, then stops.
terraform_failed() { # terraform_failed dir
  cat >&2 <<EOF

Terraform stopped with an error in $1 (the error is printed above).
- If it says "Error acquiring the state lock": another Terraform run holds the lock, or an
  earlier run was interrupted. Make sure no other Terraform is running, then release it with
  the Lock ID printed in the error, and re-run this script:
    (cd $1 && terraform force-unlock <Lock ID>)
- If it says an API "has not been used in project ... or it is disabled": the API was just
  switched on and Google needs a minute. Wait one minute and re-run this script.
- If it names a Pub/Sub service agent (gcp-sa-pubsub) that does not exist: wait one minute and
  re-run; the script asks Google to create that agent before each apply.
- If you answered anything but yes at Terraform's prompt: nothing changed. Re-run this script
  when you are ready.
Re-running is safe: finished steps are skipped and Terraform applies only what is missing.
EOF
  exit 1
}

# Pub/Sub's service agent is created lazily by Google. Terraform grants it roles, so make sure
# it exists before applying (idempotent).
ensure_pubsub_agent() { # ensure_pubsub_agent project
  gcloud services enable pubsub.googleapis.com --project="$1"
  gcloud beta services identity create --service=pubsub.googleapis.com --project="$1" >/dev/null
}

tf_out() { # tf_out dir name
  local v
  v="$(terraform -chdir="$1" output -raw "$2")"
  if [[ -z "$v" || "$v" == *$'\n'* || "$v" == *" "* ]]; then
    stop "Terraform output $2 in $1 is empty or malformed. Run 'terraform -chdir=$1 output' to see it."
  fi
  printf '%s' "$v"
}

# ---------------------------------------------------------------- preconditions
if ! terraform version 2>/dev/null | grep -q '^Terraform v'; then
  stop "Terraform is not installed in ~/bin. Run 'bash ops/scripts/00-bootstrap.sh' once (it installs it), then re-run this script."
fi
if [[ ! -f "$PROD_DIR/terraform.tfvars" && -f "$ROOT/infra/terraform/terraform.tfvars" ]]; then
  mv "$ROOT/infra/terraform/terraform.tfvars" "$PROD_DIR/terraform.tfvars"   # root moved in Stage 1
fi
if [[ ! -f "$PROD_DIR/terraform.tfvars" ]]; then
  stop "$PROD_DIR/terraform.tfvars is missing. It is written by Stage 0: run 'bash ops/scripts/00-bootstrap.sh' first."
fi
for v in project_id billing_account_id alert_email; do
  if [[ -z "$(tfvar_line "$PROD_DIR/terraform.tfvars" "$v")" ]]; then
    stop "The variable $v is missing from $PROD_DIR/terraform.tfvars. Add a line '$v = \"...\"' (see terraform.tfvars.example next to it), then re-run."
  fi
done

# Both applies need the Cloudflare token (dev.<domain> moves between the two roots).
if [[ -z "${TF_VAR_cloudflare_api_token:-}" ]]; then
  echo "Terraform needs your Cloudflare API token (the one from Stage 0: Zone:DNS:Edit on $DOMAIN)."
  echo "Paste it and press Enter. Nothing is shown while you paste, and it is not saved anywhere."
  read -rs -p "Cloudflare API token: " TF_VAR_cloudflare_api_token
  echo
  export TF_VAR_cloudflare_api_token
fi
if [[ -z "$TF_VAR_cloudflare_api_token" || "$TF_VAR_cloudflare_api_token" == *" "* ]]; then
  stop "The Cloudflare token is empty or contains a space. Create one (Cloudflare > My Profile > API Tokens > 'Edit zone DNS', zone $DOMAIN) and re-run."
fi

# ---------------------------------------------------------------- 1. folder
say "1/8 Folder ${FOLDER_NAME}"
ORG_ID="${ORG_ID:-$(gcloud projects get-ancestors "$PROD_PROJECT" --format='value(id,type)' | awk '$2 == "organization" { print $1 }')}"
if [[ -z "$ORG_ID" ]]; then
  stop "Could not find the organisation above ${PROD_PROJECT}. Re-run with ORG_ID=<organisation number> in front (list: gcloud organizations list)."
fi
find_folder() {
  local f
  f="$(gcloud resource-manager folders list --organization="$ORG_ID" \
        --filter="displayName=${FOLDER_NAME}" --format='value(name)' | head -1)"
  printf '%s' "${f##*/}"
}
FOLDER_ID="$(find_folder)"
if [[ -z "$FOLDER_ID" ]]; then
  if ! gcloud resource-manager folders create --display-name="$FOLDER_NAME" --organization="$ORG_ID" >/dev/null; then
    stop "Google refused to create the folder. Your account needs the role 'Folder Creator' (roles/resourcemanager.folderCreator) on the organisation; an organisation administrator can grant it. Then re-run."
  fi
  for _ in 1 2 3 4 5 6; do FOLDER_ID="$(find_folder)"; [[ -n "$FOLDER_ID" ]] && break; sleep 5; done
  [[ -n "$FOLDER_ID" ]] || stop "The folder was requested but is not visible yet. Wait a minute and re-run."
  echo "Created folder ${FOLDER_NAME}."
else
  echo "Folder ${FOLDER_NAME} exists."
fi

parent_of() { gcloud projects describe "$1" --format='value(parent.type,parent.id)' | tr '\t' '/'; }
if [[ "$(parent_of "$PROD_PROJECT")" == "folder/${FOLDER_ID}" ]]; then
  echo "${PROD_PROJECT} is already in the folder."
else
  echo "${PROD_PROJECT} is not in the folder yet. Moving it keeps its id, its services and its data;"
  echo "nothing restarts. Access granted on the folder starts to apply to it."
  read -r -p "Move ${PROD_PROJECT} into the folder ${FOLDER_NAME} now? [y/N] " ANSWER
  if [[ "$ANSWER" == "y" || "$ANSWER" == "Y" ]]; then
    if ! gcloud beta projects move "$PROD_PROJECT" --folder="$FOLDER_ID" --quiet; then
      stop "Google refused the move. Your account needs 'Project Mover' (roles/resourcemanager.projectMover) on the project or its current parent, and permission to move projects into the folder ('Project Creator', roles/resourcemanager.projectCreator, on the folder ${FOLDER_NAME}). Grant them and re-run, or re-run and answer N to continue without moving."
    fi
  else
    echo "Not moved. Re-run the script later to move it; everything else continues."
  fi
fi

# ---------------------------------------------------------------- 2. dev project
say "2/8 Project ${DEV_PROJECT}"
if ! gcloud projects describe "$DEV_PROJECT" >/dev/null 2>&1; then
  if ! gcloud projects create "$DEV_PROJECT" --folder="$FOLDER_ID" --name="AuDHD Neurobiology dev"; then
    stop "Google refused to create ${DEV_PROJECT}. Either the id is taken by someone else (re-run with DEV_PROJECT=<another id> in front), or your account needs 'Project Creator' (roles/resourcemanager.projectCreator) on the folder."
  fi
else
  if [[ "$(parent_of "$DEV_PROJECT")" != "folder/${FOLDER_ID}" ]]; then
    echo "Note: ${DEV_PROJECT} exists but is not in the folder ${FOLDER_NAME}. Move it with:"
    echo "  gcloud beta projects move ${DEV_PROJECT} --folder=${FOLDER_ID}"
  fi
fi
BILLING_ACCOUNT="${BILLING_ACCOUNT:-$(gcloud billing projects describe "$PROD_PROJECT" --format='value(billingAccountName)' | sed 's#billingAccounts/##')}"
if [[ -z "$BILLING_ACCOUNT" ]]; then
  stop "${PROD_PROJECT} has no billing account to share. Re-run with BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX in front (list: gcloud billing accounts list)."
fi
CURRENT="$(gcloud billing projects describe "$DEV_PROJECT" --format='value(billingAccountName)' | sed 's#billingAccounts/##')"
if [[ "$CURRENT" != "$BILLING_ACCOUNT" ]]; then
  gcloud billing projects link "$DEV_PROJECT" --billing-account="$BILLING_ACCOUNT" >/dev/null
  echo "Linked ${DEV_PROJECT} to the billing account of ${PROD_PROJECT}."
else
  echo "Billing is linked."
fi
# Switched on here, ahead of Terraform, so the first dev apply does not race APIs that were
# switched on a moment earlier (service accounts, the GitHub identity, Pub/Sub, Firestore).
gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com \
  storage.googleapis.com artifactregistry.googleapis.com run.googleapis.com \
  iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  pubsub.googleapis.com firestore.googleapis.com \
  --project="$DEV_PROJECT"

# ---------------------------------------------------------------- 3. dev state bucket
say "3/8 Terraform state bucket for dev"
DEV_BUCKET="${DEV_PROJECT}-tfstate"
if ! gcloud storage buckets describe "gs://${DEV_BUCKET}" --project="$DEV_PROJECT" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${DEV_BUCKET}" --project="$DEV_PROJECT" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
fi
gcloud storage buckets update "gs://${DEV_BUCKET}" --versioning >/dev/null
echo "gs://${DEV_BUCKET}: versioning on, public access prevented."

# ---------------------------------------------------------------- 4. prod
say "4/8 Terraform in envs/prod"
cat <<EOF
The plan below should DESTROY the old preview site in the prod project: the Cloud Run service
web-dev, the domain mapping dev.${DOMAIN} and its Cloudflare record (if domains are mapped).
dev.${DOMAIN} is unavailable from here until step 5 has run and its new certificate is issued.
It should CREATE the platform: Firestore, the Pub/Sub topics, platform-api, platform-hooks,
the job platform-selfcheck, their service accounts and permissions.
Read the plan, then type yes at Terraform's prompt to apply it (anything else cancels).
EOF
ensure_pubsub_agent "$PROD_PROJECT"
terraform -chdir="$PROD_DIR" init -input=false -backend-config="bucket=${PROD_PROJECT}-tfstate" \
  || terraform_failed "$PROD_DIR"
terraform -chdir="$PROD_DIR" apply || terraform_failed "$PROD_DIR"
PROD_REGISTRY="$(tf_out "$PROD_DIR" artifact_registry)"
PROD_WIF="$(tf_out "$PROD_DIR" wif_provider)"
PROD_DEPLOYER="$(tf_out "$PROD_DIR" deployer_service_account)"
PROD_RUNTIME="$(tf_out "$PROD_DIR" web_runtime_service_account)"

# ---------------------------------------------------------------- 5. dev
say "5/8 Terraform in envs/dev"
DEV_TFVARS="$DEV_DIR/terraform.tfvars"
if [[ ! -f "$DEV_TFVARS" ]]; then
  # The alert email is taken from the prod settings, or from the account you are logged in
  # with, and written only to this git-ignored file. It is not printed.
  ALERT_LINE="$(tfvar_line "$PROD_DIR/terraform.tfvars" alert_email)"
  if [[ -z "$ALERT_LINE" ]]; then
    ALERT_LINE="alert_email = \"$(gcloud config get-value account 2>/dev/null)\""
  fi
  {
    echo "project_id = \"${DEV_PROJECT}\""
    echo "region = \"${REGION}\""
    echo "$ALERT_LINE"
    echo "github_repository = \"${GITHUB_REPO}\""
    # Same domain settings as prod: if prod maps its domains, dev maps dev.<domain>.
    for v in domain map_custom_domains manage_cloudflare_dns cloudflare_zone_id; do
      tfvar_line "$PROD_DIR/terraform.tfvars" "$v"
    done
  } > "$DEV_TFVARS"
  echo "Wrote $DEV_TFVARS (git-ignored)."
fi
if ! grep -qE '^alert_email[[:space:]]*=[[:space:]]*"[^"]+"' "$DEV_TFVARS"; then
  stop "The variable alert_email is missing or empty in $DEV_TFVARS. Add a line 'alert_email = \"...\"' (where dead-letter alerts go), then re-run."
fi
cat <<EOF
The plan below should CREATE the dev project's resources: APIs, the image registry, web-dev,
the GitHub identity for dev deploys, Firestore, the Pub/Sub topics, platform-api,
platform-hooks, platform-selfcheck and (if domains are mapped) dev.${DOMAIN}.
Type yes at Terraform's prompt to apply it.
EOF
ensure_pubsub_agent "$DEV_PROJECT"
terraform -chdir="$DEV_DIR" init -input=false -backend-config="bucket=${DEV_BUCKET}" \
  || terraform_failed "$DEV_DIR"
terraform -chdir="$DEV_DIR" apply || terraform_failed "$DEV_DIR"
DEV_REGISTRY="$(tf_out "$DEV_DIR" artifact_registry)"
DEV_WIF="$(tf_out "$DEV_DIR" wif_provider)"
DEV_DEPLOYER="$(tf_out "$DEV_DIR" deployer_service_account)"
DEV_RUNTIME="$(tf_out "$DEV_DIR" web_runtime_service_account)"

# ---------------------------------------------------------------- 6. first images
say "6/8 First images: web-dev, then platform-api"
TAG="$(git -C "$ROOT" rev-parse --short=12 HEAD)"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

push_image() { # push_image image
  local i
  for i in 1 2 3 4 5; do
    docker push "$1" && return 0
    [[ $i == 5 ]] && stop "Pushing $1 failed five times. Re-run the script."
    echo "push failed, retrying in $((i * 10))s"; sleep $((i * 10))
  done
}

# The website in the dev project. Terraform created web-dev with Google's placeholder image;
# CI deploys to it only after Gate 1, so the script puts the current site there now.
WEB_IMAGE="${DEV_REGISTRY}/web:${TAG}"
docker build -t "$WEB_IMAGE" "$ROOT/apps/web"
push_image "$WEB_IMAGE"
gcloud run deploy web-dev --image="$WEB_IMAGE" --region="$REGION" --project="$DEV_PROJECT" \
  --service-account="$DEV_RUNTIME" --quiet
echo "web-dev runs the website at commit ${TAG}."

PLATFORM_IMAGE_SKIPPED=""
if [[ ! -f "$ROOT/services/platform-api/Dockerfile" ]]; then
  PLATFORM_IMAGE_SKIPPED="yes"
  cat <<EOF
The platform-api service is not in this branch yet (services/platform-api/Dockerfile is
missing), so its image cannot be built now. Nothing is broken: Terraform created the services
and the job with Google's placeholder image. Re-run this script once Core's service code and
the platform-api image (S1.0 Task 6) have been merged; the platform-api CI deploy arrives with
that task too. Continuing with step 7.
EOF
else
  docker build -t "platform-api:${TAG}" "$ROOT/services/platform-api"
  deploy_platform() { # deploy_platform project registry
    local image="$2/platform-api:${TAG}"
    docker tag "platform-api:${TAG}" "$image"
    push_image "$image"
    # Only the image changes; every other setting belongs to Terraform.
    for svc in platform-api platform-hooks; do
      gcloud run deploy "$svc" --image="$image" --region="$REGION" --project="$1" --quiet
    done
    gcloud run jobs update platform-selfcheck --image="$image" --region="$REGION" --project="$1" --quiet
  }
  deploy_platform "$DEV_PROJECT" "$DEV_REGISTRY"
  deploy_platform "$PROD_PROJECT" "$PROD_REGISTRY"
fi

# ---------------------------------------------------------------- 7. GitHub environments
say "7/8 GitHub environments dev and production"
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  for envname in dev production; do
    # Created only when absent, so protection rules you already set are left alone.
    if ! gh api "repos/${GITHUB_REPO}/environments/${envname}" >/dev/null 2>&1; then
      gh api -X PUT "repos/${GITHUB_REPO}/environments/${envname}" --silent
      echo "Created environment ${envname}."
    fi
  done
  set_env_vars() { # set_env_vars env project wif deployer runtime registry
    gh variable set GCP_PROJECT_ID --env "$1" --repo "$GITHUB_REPO" --body "$2"
    gh variable set GCP_REGION     --env "$1" --repo "$GITHUB_REPO" --body "$REGION"
    gh variable set WIF_PROVIDER   --env "$1" --repo "$GITHUB_REPO" --body "$3"
    gh variable set DEPLOYER_SA    --env "$1" --repo "$GITHUB_REPO" --body "$4"
    gh variable set RUNTIME_SA     --env "$1" --repo "$GITHUB_REPO" --body "$5"
    gh variable set REGISTRY       --env "$1" --repo "$GITHUB_REPO" --body "$6"
  }
  set_env_vars dev "$DEV_PROJECT" "$DEV_WIF" "$DEV_DEPLOYER" "$DEV_RUNTIME" "$DEV_REGISTRY"
  set_env_vars production "$PROD_PROJECT" "$PROD_WIF" "$PROD_DEPLOYER" "$PROD_RUNTIME" "$PROD_REGISTRY"
  echo "Dev deploys stay off until Gate 1, when you run:"
  echo "  gh variable set DEPLOY_DEV_ENABLED --env dev --repo ${GITHUB_REPO} --body true"
else
  echo "gh is not logged in. Run 'gh auth login', then re-run this script (finished steps are skipped)."
fi

# ---------------------------------------------------------------- 8. reminder
say "8/8 Protect production"
REVIEWERS=""
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  REVIEWERS="$(gh api "repos/${GITHUB_REPO}/environments/production" \
    --jq '[.protection_rules[]? | select(.type == "required_reviewers") | .reviewers[]?] | length' 2>/dev/null || true)"
fi
if [[ -n "$REVIEWERS" && "$REVIEWERS" != "0" ]]; then
  echo "The production environment has ${REVIEWERS} required reviewer(s). Check it is you:"
  echo "  GitHub > ${GITHUB_REPO} > Settings > Environments > production"
else
  cat <<EOF
Production deploys must wait for your approval. Make yourself the required reviewer of the
production environment (GitHub > ${GITHUB_REPO} > Settings > Environments > production >
Required reviewers), or run:
  gh api -X PUT repos/${GITHUB_REPO}/environments/production \\
    -f 'reviewers[][type]=User' -F "reviewers[][id]=\$(gh api user -q .id)"
EOF
fi

say "Done"
if [[ -n "$PLATFORM_IMAGE_SKIPPED" ]]; then
  cat <<EOF
platform-api still runs Google's placeholder image, so the smoke test cannot pass yet. It runs
only after Core's service code and the platform-api image (S1.0 Task 6) have landed: then
re-run this script (step 6 deploys the image) and run
  bash ops/scripts/smoke-platform.sh ${DEV_PROJECT}
Now both of these should say "No changes":
EOF
else
  cat <<EOF
Next: bash ops/scripts/smoke-platform.sh ${DEV_PROJECT}
Then both of these should say "No changes":
EOF
fi
cat <<EOF
  terraform -chdir=infra/terraform/envs/prod plan
  terraform -chdir=infra/terraform/envs/dev plan
EOF
