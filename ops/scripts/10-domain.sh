#!/usr/bin/env bash
# Stage 0, part 2: put the site on audhdneurobiology.org (Cloudflare DNS, Cloud Run domain mapping).
# Run in Cloud Shell from the repository root after 00-bootstrap.sh:
#   export TF_VAR_cloudflare_api_token=...    # Cloudflare token with Zone:DNS:Edit on the zone
#   bash ops/scripts/10-domain.sh
set -euo pipefail

export PATH="$HOME/bin:$PATH"   # Terraform installed by 00-bootstrap.sh
DOMAIN="${DOMAIN:-audhdneurobiology.org}"
ROOT="$(git rev-parse --show-toplevel)"
TFVARS="$ROOT/infra/terraform/terraform.tfvars"

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
setvar() { # setvar name value  (replace or append a line in terraform.tfvars)
  if grep -q "^$1 *=" "$TFVARS"; then sed -i "s#^$1 *=.*#$1 = $2#" "$TFVARS"; else echo "$1 = $2" >> "$TFVARS"; fi
}

say "1/4 Domain ownership"
if gcloud domains list-user-verified --format='value(id)' | grep -qx "$DOMAIN"; then
  echo "$DOMAIN is verified for $(gcloud config get-value account)."
else
  cat <<EOF
$DOMAIN is not verified yet. This is the one step Google requires a browser for.
  1. Run:  gcloud domains verify $DOMAIN
     It prints a Search Console link. Open it, choose 'Domain', provider 'Cloudflare'.
  2. Search Console shows a TXT record 'google-site-verification=...'.
     Either let it add the record through Cloudflare's sign-in, or add it yourself:
       Cloudflare > audhdneurobiology.org > DNS > Add record > TXT, name @, content = that string.
  3. Click Verify, then re-run this script.
EOF
  exit 1
fi

say "2/4 Cloudflare zone"
if [[ -z "${TF_VAR_cloudflare_api_token:-}" ]]; then
  echo "Set TF_VAR_cloudflare_api_token first (Cloudflare > My Profile > API Tokens > Create Token > 'Edit zone DNS' template, zone $DOMAIN)."
  exit 1
fi
ZONE_ID="$(curl -fsS -H "Authorization: Bearer ${TF_VAR_cloudflare_api_token}" \
  "https://api.cloudflare.com/client/v4/zones?name=${DOMAIN}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"][0]["id"])')"
echo "zone id: $ZONE_ID"

say "3/4 Terraform: domain mappings and DNS records"
setvar map_custom_domains true
setvar manage_cloudflare_dns true
setvar cloudflare_zone_id "\"$ZONE_ID\""
cd "$ROOT/infra/terraform"
terraform apply -input=false
terraform output domain_records

say "4/4 Waiting for certificates (usually 15-60 minutes)"
for host in "$DOMAIN" "www.$DOMAIN" "dev.$DOMAIN"; do
  echo "- $host: $(gcloud beta run domain-mappings describe --domain "$host" --region asia-southeast1 \
      --format='value(status.conditions[0].type,status.conditions[0].status,status.conditions[0].message)' 2>/dev/null || echo pending)"
done
cat <<EOF

Re-check with:
  curl -sI https://$DOMAIN/api/healthz | head -1
When it returns 200, point the uptime check at the real domain:
  sed -i 's#^check_custom_domain *=.*#check_custom_domain = true#' infra/terraform/terraform.tfvars || echo 'check_custom_domain = true' >> infra/terraform/terraform.tfvars
  (cd infra/terraform && terraform apply)
EOF
