variable "project_id" {
  type        = string
  description = "Project that holds Identity Platform"
}

variable "authorized_domains" {
  type        = list(string)
  description = "Hosts that may start sign-in (for example the site's own host names)"
}
