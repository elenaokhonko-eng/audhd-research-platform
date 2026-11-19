variable "name" {
  description = "Cloud Run service name, e.g. platform-api"
  type        = string
}

variable "project_id" {
  description = "Google Cloud project id"
  type        = string
}

variable "region" {
  description = "Region of the service"
  type        = string
}

variable "image" {
  description = "Image used when the service is first created. CI deploys the real image; later changes are ignored."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "service_account_email" {
  description = "Identity the service runs as (declared in the root's identities.tf)"
  type        = string
}

variable "public" {
  description = "Serve without an invoker check (invoker_iam_disabled). Never an allUsers binding."
  type        = bool
  default     = false
}

variable "env" {
  description = "Plain environment variables. No secrets: those come from Secret Manager."
  type        = map(string)
  default     = {}
}

variable "invokers" {
  description = "Service account emails granted roles/run.invoker on a private service. Ignored when public."
  type        = list(string)
  default     = []
}

variable "deletion_protection" {
  description = "Refuse terraform destroy of the service (on in prod)"
  type        = bool
  default     = false
}
