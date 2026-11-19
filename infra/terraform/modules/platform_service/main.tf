# One Cloud Run service of platform-api's image. Terraform owns its shape (scaling, identity,
# probes, env, who may call it); GitHub Actions owns which image runs, so the image is
# ignored after creation, as in modules/web_service.

resource "google_cloud_run_v2_service" "this" {
  project             = var.project_id
  name                = var.name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection

  # A public service has no allUsers binding. Organisations with domain restricted sharing
  # refuse allUsers; disabling the invoker check is Google's supported way (ADR 0005).
  # A private service keeps the check and names its callers below.
  invoker_iam_disabled = var.public

  # Extra audiences Cloud Run accepts in identity tokens, besides its own URLs.
  custom_audiences = var.custom_audiences

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      # Placeholder until the first CI deploy replaces it.
      image = var.image

      ports {
        container_port = 8080
      }

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
        cpu_idle = true
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 0
        period_seconds        = 3
        failure_threshold     = 10
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      template[0].revision,
      client,
      client_version,
    ]
  }
}

# Callers of a private service. Each is a service account listed in the root's identities.tf.
# count, not for_each: the emails of accounts created in the same apply are unknown at plan
# time, and for_each needs its keys at plan time; the length of the list is known.
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  count    = var.public ? 0 : length(var.invokers)
  project  = var.project_id
  location = google_cloud_run_v2_service.this.location
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.invokers[count.index]}"
}
