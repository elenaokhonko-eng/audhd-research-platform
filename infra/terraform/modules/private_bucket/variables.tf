variable "name" {
  type        = string
  description = "Bucket name (globally unique)."
}

variable "project_id" {
  type        = string
  description = "Project that holds the bucket."
}

variable "location" {
  type        = string
  description = "Bucket location (ADR 0001: Singapore)."
  default     = "ASIA-SOUTHEAST1"
}

variable "versioning" {
  type        = bool
  description = "Keep earlier versions of overwritten or deleted objects."
  default     = false
}

variable "delete_after_days" {
  type        = number
  description = "Delete objects this many days after creation. Null keeps them forever."
  default     = null
}

variable "force_destroy" {
  type        = bool
  description = "Allow Terraform to delete the bucket while it still holds objects. Dev scratch buckets only."
  default     = false
}
