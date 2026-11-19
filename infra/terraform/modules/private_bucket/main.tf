# A private bucket: no public access, ever. Who may read or write is bound in the root's
# identities.tf; this module only returns the name.

resource "google_project_service" "storage" {
  project            = var.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_storage_bucket" "this" {
  project                     = var.project_id
  name                        = var.name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy

  versioning {
    enabled = var.versioning
  }

  dynamic "lifecycle_rule" {
    for_each = var.delete_after_days == null ? [] : [var.delete_after_days]
    content {
      condition {
        age = lifecycle_rule.value
      }
      action {
        type = "Delete"
      }
    }
  }

  depends_on = [google_project_service.storage]
}
