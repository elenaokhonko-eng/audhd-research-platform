variable "project_id" {
  description = "Google Cloud project id, e.g. audhd-neurobiology-dev"
  type        = string
}

variable "region" {
  description = "Region for every regional resource (ADR 0001: Singapore)"
  type        = string
  default     = "asia-southeast1"
}

variable "alert_email" {
  description = "Where dead-letter alerts go"
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
  description = "Create the Cloud Run domain mapping for dev.<domain>. Needs the domain verified in Search Console by the identity running Terraform."
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

variable "owner_member" {
  description = "IAM member of the owner, e.g. user:name@example.org. Set via TF_VAR_owner_member; never written to a file."
  type        = string
  sensitive   = true
}

variable "auth_email_spf_includes" {
  description = "Hosts in the one SPF record of the sign-in email domain. Add any includes the domain already carries (dig +short TXT <domain>)."
  type        = list(string)
  default     = ["_spf.firebasemail.com"]
}

variable "auth_email_dkim_targets" {
  description = "Override of the two DKIM CNAME targets (selector to host), if the console's customize-domain screen differs from the computed pattern. Null computes them."
  type        = map(string)
  default     = null
}

variable "signin_sender_hint" {
  description = "Sender address the sign-in email shows, once the first test email reveals it. Given to the web service as SIGNIN_SENDER_HINT."
  type        = string
  default     = ""
}
