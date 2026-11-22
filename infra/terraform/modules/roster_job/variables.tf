variable "project_id" {
  type        = string
  description = "Project that holds the job."
}

variable "region" {
  type        = string
  description = "Region of the job."
}

variable "image" {
  type        = string
  description = "Image used when the job is first created. CI deploys the real image; later changes are ignored."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "env" {
  type        = map(string)
  description = "Plain environment variables. No secret values."
  default     = {}
}

variable "job_service_account_email" {
  type        = string
  description = "Identity the job runs as (job-substack, declared in the root's identities.tf)."
}

variable "roster_inbox_bucket" {
  type        = string
  description = "Name of the bucket where the owner drops the roster export. The job may read its objects."
}

variable "owner_member" {
  type        = string
  description = "IAM member of the owner, e.g. user:name@example.org. The only one who may start the import."
  sensitive   = true
}

variable "runner_role_id" {
  type        = string
  description = "Custom role platformJobRunner (start a job and follow its executions), from the root's identities.tf."
}

variable "overrides_role" {
  type        = string
  description = "Role that may start a run with changed settings (roles/run.jobsExecutorWithOverrides). Bound for the owner only."
}

variable "deletion_protection" {
  type        = bool
  description = "Refuse terraform destroy of the job (on in prod, off in dev)."
  default     = true
}
