variable "project_id" {
  description = "Project that holds the Firestore database"
  type        = string
}

variable "database" {
  description = "Firestore database the indexes and time-to-live policies belong to"
  type        = string
  default     = "(default)"
}
