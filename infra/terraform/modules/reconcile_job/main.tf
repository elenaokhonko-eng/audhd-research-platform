# The Stripe reconcile: a Cloud Run job that reads Stripe with a restricted, read-only key and
# records what it finds. Its own identity is the only reader of the key. platform-api, the
# owner and the scheduler may start it; only the owner may start a run with changed settings
# (the dry run). The schedule is created paused.

locals {
  job_name = "stripe-reconcile"

  # Built from the inputs, so it is known at plan time. The job reads the latest version;
  # the owner adds it from her terminal (Terraform creates the container only).
  key_secret_version = "projects/${var.project_id}/secrets/stripe-read-key/versions/latest"
}

# ---------------------------------------------------------------- the Stripe key
# No version here: a value in Terraform would be a value in state.
resource "google_secret_manager_secret" "stripe" {
  project   = var.project_id
  secret_id = "stripe-read-key"

  # Kept in the platform's region only (automatic replication would copy it elsewhere).
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

# Authoritative for the accessor role on this secret: the member list is exactly the job.
resource "google_secret_manager_secret_iam_binding" "readers" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.stripe.secret_id
  role      = "roles/secretmanager.secretAccessor"
  members   = ["serviceAccount:${var.job_service_account_email}"]
}

# ---------------------------------------------------------------- the job
resource "google_cloud_run_v2_job" "this" {
  project  = var.project_id
  name     = local.job_name
  location = var.region

  template {
    task_count = 1
    template {
      service_account = var.job_service_account_email
      # A failed reconcile is not retried blindly; the next scheduled run starts afresh.
      max_retries = 0
      # Under the shortest allowed schedule period (10 minutes), so two runs never overlap.
      timeout = "540s"

      containers {
        # Placeholder until the first CI deploy replaces it.
        image   = var.image
        command = ["platform-cli"]
        args    = ["job", local.job_name]

        dynamic "env" {
          for_each = merge(var.env, { PLATFORM_STRIPE_KEY_SECRET = local.key_secret_version })
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

# Who may start the job: platform-api (a member's refresh), the owner and the scheduler.
# Authoritative for the role on this job.
resource "google_cloud_run_v2_job_iam_binding" "runners" {
  project  = var.project_id
  location = google_cloud_run_v2_job.this.location
  name     = google_cloud_run_v2_job.this.name
  role     = var.runner_role_id
  members = [
    "serviceAccount:${var.api_service_account_email}",
    var.owner_member,
    "serviceAccount:${var.scheduler_service_account_email}",
  ]
}

# Who may start a run with changed settings (the dry run): the owner alone.
resource "google_cloud_run_v2_job_iam_binding" "overrides" {
  project  = var.project_id
  location = google_cloud_run_v2_job.this.location
  name     = google_cloud_run_v2_job.this.name
  role     = var.overrides_role
  members  = [var.owner_member]
}

# ---------------------------------------------------------------- the schedule
# Calls the Run Admin API's :run with an OAuth token of the scheduler's identity (Google APIs
# on *.googleapis.com take OAuth tokens, not identity tokens). The body is empty: an override
# would need the permission only the owner has, and the job's own default records the run as
# scheduled. Cloud Scheduler's service agent mints the token; it needs no extra grant.
resource "google_cloud_scheduler_job" "reconcile" {
  project   = var.project_id
  region    = var.region
  name      = local.job_name
  schedule  = var.schedule
  time_zone = "Etc/UTC"
  paused    = !var.schedule_enabled

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.this.name}:run"

    oauth_token {
      service_account_email = var.scheduler_service_account_email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }
}
