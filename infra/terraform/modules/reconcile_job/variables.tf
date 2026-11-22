variable "project_id" {
  type        = string
  description = "Project that holds the job, the secret and the schedule."
}

variable "region" {
  type        = string
  description = "Region of the job, the secret's single replica and the schedule."
}

variable "image" {
  type        = string
  description = "Image used when the job is first created. CI deploys the real image; later changes are ignored."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "env" {
  type        = map(string)
  description = "Plain environment variables. No secret values: the job reads the Stripe key from Secret Manager."
  default     = {}
}

variable "job_service_account_email" {
  type        = string
  description = "Identity the job runs as (job-stripe, declared in the root's identities.tf). The only reader of the Stripe key."
}

variable "api_service_account_email" {
  type        = string
  description = "platform-api's identity. It may start the job; it may not change a run's settings or read the key."
}

variable "owner_member" {
  type        = string
  description = "IAM member of the owner, e.g. user:name@example.org. May start the job, with or without changed settings."
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

variable "schedule" {
  type        = string
  description = "Cron schedule of the reconcile, in UTC. Its period must be at least 10 minutes, so two runs never overlap."
  default     = "*/30 * * * *"

  # The job may run for up to 540 seconds, so two starts must be at least 10 minutes apart.
  # Five fields are required. The minute field is accepted in two forms only:
  #   */N         every N minutes from minute 0, e.g. */10 or */30;
  #   M or M,M,…  fixed minutes of the hour, e.g. 7 or 0,20,40.
  # Either form is turned into its list of minutes, and every gap between two consecutive
  # minutes, including the one across the hour (last minute to the first of the next hour),
  # must be at least 10. So */5 and 0,5 are refused, and so is */55 (55 then 0 is 5 apart).
  # Ranges and other forms are refused rather than interpreted.
  validation {
    condition = try(alltrue([
      for minutes in [
        for field in [regexall("\\S+", var.schedule)[0]] : (
          startswith(field, "*/")
          ? tolist(range(0, 60, tonumber(trimprefix(field, "*/"))))
          : tolist([for s in sort([for m in split(",", field) : format("%02d", tonumber(m))]) : tonumber(s)])
        )
      ] :
      length(regexall("\\S+", var.schedule)) == 5
      && alltrue([for m in minutes : m >= 0 && m <= 59 && floor(m) == m])
      && alltrue([for i in range(length(minutes)) : (i == length(minutes) - 1 ? minutes[0] + 60 : minutes[i + 1]) - minutes[i] >= 10])
    ]), false)
    error_message = "The schedule's minute field must be */N or a list of fixed minutes, with at least 10 minutes between two starts (for example */30 * * * *)."
  }
}

variable "schedule_enabled" {
  type        = bool
  description = "Run the schedule. Off by default: the launch runbook switches it on after the first good real run."
  default     = false
}

variable "scheduler_service_account_email" {
  type        = string
  description = "Identity Cloud Scheduler uses to start the job. It holds the runner role on this job and nothing else."
}
