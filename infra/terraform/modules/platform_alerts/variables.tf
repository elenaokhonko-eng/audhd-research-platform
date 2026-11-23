variable "project_id" {
  type        = string
  description = "Project whose logs and metrics the alerts watch."
}

variable "notification_channel_ids" {
  type        = list(string)
  description = "Notification channels every alert notifies: the owner's email channel."
}

variable "accept_test_log" {
  type        = bool
  description = "Whether the log filters also accept entries of the log platform-test, which ops/scripts/42-raise-test-alert.sh writes. True in dev, false in prod."
  default     = false
}
