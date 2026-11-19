variable "project_id" {
  description = "Google Cloud project id"
  type        = string
}

variable "push_endpoint_base" {
  description = "Base URL of platform-api; push routes are appended (/internal/pubsub/...)"
  type        = string
}

variable "push_service_account_email" {
  description = "Identity Pub/Sub signs push requests as (pubsub-push)"
  type        = string
}

variable "push_audience" {
  description = "Audience of the OIDC token on each push; platform-api checks it (PLATFORM_PUSH_AUDIENCE)"
  type        = string
}
