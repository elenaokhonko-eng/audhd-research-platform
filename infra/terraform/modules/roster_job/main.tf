# The roster import: a Cloud Run job, started by the owner only, that reads the newest roster
# export in the roster inbox and records paid Substack readers. It is not scheduled.

locals {
  job_name = "roster-import"
}

# The job reads the files in the roster inbox. It cannot write or delete them; the bucket's
# own lifecycle empties it after seven days.
resource "google_storage_bucket_iam_member" "reads_inbox" {
  bucket = var.roster_inbox_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${var.job_service_account_email}"
}

resource "google_cloud_run_v2_job" "this" {
  project             = var.project_id
  name                = local.job_name
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    task_count = 1
    template {
      service_account = var.job_service_account_email
      # An import is not retried blindly; the owner reads the run and starts it again.
      max_retries = 0
      timeout     = "900s"

      containers {
        # Placeholder until the first CI deploy replaces it.
        image   = var.image
        command = ["platform-cli"]
        args    = ["job", local.job_name]

        dynamic "env" {
          for_each = var.env
          content {
            name  = env.key
            value = env.value
          }
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}

# Only the owner may start the import, with or without changed settings (the dry run).
# Both bindings are authoritative for their role on this job.
resource "google_cloud_run_v2_job_iam_binding" "runners" {
  project  = var.project_id
  location = google_cloud_run_v2_job.this.location
  name     = google_cloud_run_v2_job.this.name
  role     = var.runner_role_id
  members  = [var.owner_member]
}

resource "google_cloud_run_v2_job_iam_binding" "overrides" {
  project  = var.project_id
  location = google_cloud_run_v2_job.this.location
  name     = google_cloud_run_v2_job.this.name
  role     = var.overrides_role
  members  = [var.owner_member]
}
