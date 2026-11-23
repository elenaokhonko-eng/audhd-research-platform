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

variable "stripe_substack_application" {
  description = "Stripe application id that marks a subscription as created by Substack (PLATFORM_STRIPE_SUBSTACK_APPLICATION of the two jobs). Set in terraform.tfvars; never committed."
  type        = string
  default     = ""
}

variable "substack_grant_month" {
  description = "What a paying Substack reader on a monthly plan is recorded as: tier:paid or status:substack_paid (the owner's commercial decision)"
  type        = string
  default     = "status:substack_paid"
  validation {
    condition     = contains(["tier:paid", "status:substack_paid"], var.substack_grant_month)
    error_message = "substack_grant_month must be tier:paid or status:substack_paid."
  }
}

variable "substack_grant_year" {
  description = "What a paying Substack reader on an annual plan is recorded as: tier:paid or status:substack_paid (the owner's commercial decision)"
  type        = string
  default     = "status:substack_paid"
  validation {
    condition     = contains(["tier:paid", "status:substack_paid"], var.substack_grant_year)
    error_message = "substack_grant_year must be tier:paid or status:substack_paid."
  }
}

variable "reconcile_schedule" {
  description = "Cron schedule (UTC) of the stripe-reconcile job; at least 10 minutes between runs. Shorten it while a campaign is open."
  type        = string
  default     = "*/30 * * * *"
}

variable "reconcile_schedule_enabled" {
  description = "Run the reconcile schedule. Created paused; the launch runbook switches it on after the first good real run."
  type        = bool
  default     = false
}
