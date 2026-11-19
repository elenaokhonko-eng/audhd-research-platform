variable "project_id" {
  description = "Google Cloud project id, e.g. audhd-neurobiology-prod"
  type        = string
}

variable "region" {
  description = "Region for every regional resource (ADR 0001: Singapore)"
  type        = string
  default     = "asia-southeast1"
}

variable "billing_account_id" {
  description = "Billing account id (XXXXXX-XXXXXX-XXXXXX) for the budget alert"
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget in the billing account's own currency; alerts at 50%, 90%, 100%"
  type        = number
  default     = 30
}

variable "alert_email" {
  description = "Where uptime and budget alerts go"
  type        = string
}

variable "github_repository" {
  description = "owner/repo allowed to deploy through Workload Identity Federation"
  type        = string
  default     = "elenaokhonko-eng/audhd-research-platform"
}

variable "domain" {
  description = "Apex domain"
  type        = string
  default     = "audhdneurobiology.org"
}

variable "map_custom_domains" {
  description = "Create Cloud Run domain mappings. Needs the domain verified in Search Console by the identity running Terraform."
  type        = bool
  default     = false
}

variable "manage_cloudflare_dns" {
  description = "Write the DNS records into Cloudflare (needs cloudflare_api_token and cloudflare_zone_id)"
  type        = bool
  default     = false
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with Zone:DNS:Edit on the zone. Set via TF_VAR_cloudflare_api_token."
  type        = string
  default     = ""
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone id for the domain (Overview page of the zone, or the API)"
  type        = string
  default     = ""
}

variable "check_custom_domain" {
  description = "Point the production uptime check at https://<domain> instead of the run.app URL. Turn on once the certificate is issued."
  type        = bool
  default     = false
}

variable "owner_member" {
  description = "IAM member of the owner, e.g. user:name@example.org. Set via TF_VAR_owner_member; never written to a file."
  type        = string
  sensitive   = true
}
