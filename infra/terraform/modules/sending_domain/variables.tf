variable "enabled" {
  description = "Write the records into Cloudflare. False when DNS is not managed here."
  type        = bool
}

variable "zone_id" {
  description = "Cloudflare zone id"
  type        = string
}

variable "zone_name" {
  description = "The zone's apex domain, for example example.org"
  type        = string
}

variable "domain" {
  description = "The sending domain: the apex or a subdomain of it"
  type        = string

  validation {
    condition     = var.domain == var.zone_name || endswith(var.domain, ".${var.zone_name}")
    error_message = "domain must be the zone apex or a subdomain of it."
  }
}

variable "project_id" {
  description = "Google project id, used in the firebase=<project> verification record"
  type        = string
}

variable "spf_includes" {
  description = "Hosts to include in the single SPF record, in order"
  type        = list(string)
  default     = ["_spf.firebasemail.com"]
}

variable "dkim_targets" {
  description = "Selector to target host for the two DKIM CNAMEs. Null computes the documented pattern; set it when the console's customize-domain screen shows different values."
  type        = map(string)
  default     = null
}

variable "dmarc_policy" {
  description = "DMARC policy: none, quarantine or reject"
  type        = string
  default     = "none"
}

variable "dmarc_report_address" {
  description = "Where aggregate DMARC reports go. Empty leaves the rua tag out."
  type        = string
  default     = ""
}
