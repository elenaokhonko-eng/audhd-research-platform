#!/usr/bin/env bash
# Stage 0 bootstrap. Run in Google Cloud Shell from the repository root:
#   bash ops/scripts/00-bootstrap.sh
# Safe to re-run: every step checks before it creates.
#
# What it does
#   1. creates the project and links billing
#   2. creates the Terraform state bucket
#   3. runs Terraform (APIs, registry, web-dev, web-prod, GitHub identity, uptime check, budget)
#   4. builds the website image and deploys it to web-dev and web-prod
#   5. sets the GitHub repository variables the deploy workflow reads
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-audhd-neurobiology-prod}"
REGION="${REGION:-asia-southeast1}"
GITHUB_REPO="${GITHUB_REPO:-elenaokhonko-eng/audhd-research-platform}"
ALERT_EMAIL="${ALERT_EMAIL:-$(gcloud config get-value account 2>/dev/null)}"
BUDGET="${BUDGET:-30}"
ROOT="$(git rev-parse --show-toplevel)"

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

say "1/5 Project ${PROJECT_ID}"
if ! gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud projects create "$PROJECT_ID" --name="AuDHD Neurobiology"
fi
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud auth application-default set-quota-project "$PROJECT_ID" >/dev/null 2>&1 || true

BILLING_ACCOUNT="${BILLING_ACCOUNT:-}"
if [[ -z "$BILLING_ACCOUNT" ]]; then
  mapfile -t ACCOUNTS < <(gcloud billing accounts list --filter=open=true --format='value(name)' | sed 's#billingAccounts/##')
  if [[ ${#ACCOUNTS[@]} -ne 1 ]]; then
    echo "Found ${#ACCOUNTS[@]} open billing accounts. Re-run with BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX"
    gcloud billing accounts list
    exit 1
  fi
  BILLING_ACCOUNT="${ACCOUNTS[0]}"
fi
CURRENT="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)' | sed 's#billingAccounts/##')"
if [[ "$CURRENT" != "$BILLING_ACCOUNT" ]]; then
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
fi
gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com \
  storage.googleapis.com artifactregistry.googleapis.com run.googleapis.com

say "2/5 Terraform state bucket"
BUCKET="${PROJECT_ID}-tfstate"
if ! gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --location="$REGION" \
    --uniform-bucket-level-access --public-access-prevention
  gcloud storage buckets update "gs://${BUCKET}" --versioning
fi

say "3/5 Terraform apply"
cd "$ROOT/infra/terraform"
if [[ ! -f terraform.tfvars ]]; then
  cat > terraform.tfvars <<EOF
project_id         = "${PROJECT_ID}"
region             = "${REGION}"
billing_account_id = "${BILLING_ACCOUNT}"
alert_email        = "${ALERT_EMAIL}"
budget_amount      = ${BUDGET}
github_repository  = "${GITHUB_REPO}"
EOF
fi
terraform init -input=false -backend-config="bucket=${BUCKET}"
terraform apply -input=false
REGISTRY="$(terraform output -raw artifact_registry)"
WIF_PROVIDER="$(terraform output -raw wif_provider)"
DEPLOYER_SA="$(terraform output -raw deployer_service_account)"
RUNTIME_SA="$(terraform output -raw web_runtime_service_account)"

say "4/5 First image and deploy"
cd "$ROOT"
TAG="$(git rev-parse --short=12 HEAD)"
IMAGE="${REGISTRY}/web:${TAG}"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build -t "$IMAGE" apps/web
docker push "$IMAGE"
for SVC in web-dev web-prod; do
  gcloud run deploy "$SVC" --image "$IMAGE" --region "$REGION" \
    --service-account "$RUNTIME_SA" --quiet
done

say "5/5 GitHub repository variables"
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
  gh variable set GCP_PROJECT_ID --repo "$GITHUB_REPO" --body "$PROJECT_ID"
  gh variable set GCP_REGION     --repo "$GITHUB_REPO" --body "$REGION"
  gh variable set WIF_PROVIDER   --repo "$GITHUB_REPO" --body "$WIF_PROVIDER"
  gh variable set DEPLOYER_SA    --repo "$GITHUB_REPO" --body "$DEPLOYER_SA"
  gh variable set RUNTIME_SA     --repo "$GITHUB_REPO" --body "$RUNTIME_SA"
  gh variable set REGISTRY       --repo "$GITHUB_REPO" --body "$REGISTRY"
else
  echo "gh is not logged in. Run 'gh auth login', then re-run this script (steps 1-4 are skipped when done)."
fi

cd "$ROOT/infra/terraform"
say "Done"
echo "dev:  $(terraform output -raw web_dev_url)"
echo "prod: $(terraform output -raw web_prod_url)"
echo "Next: bash ops/scripts/10-domain.sh"
