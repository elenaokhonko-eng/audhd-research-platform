# One public Cloud Run service. Terraform owns its shape (scaling, identity, probes, env);
# GitHub Actions owns which image runs, so the image is ignored after creation.

variable "name" { type = string }
variable "region" { type = string }
variable "site_env" { type = string }
variable "service_account" { type = string }
variable "max_instances" {
  type    = number
  default = 5
}

resource "google_cloud_run_v2_service" "this" {
  name                = var.name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.site_env == "prod"

  template {
    service_account = var.service_account

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      # Placeholder until the first CI deploy replaces it.
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      env {
        name  = "SITE_ENV"
        value = var.site_env
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
          path = "/api/healthz"
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

# Public website: anyone may invoke it.
resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.this.name
  location = google_cloud_run_v2_service.this.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "name" { value = google_cloud_run_v2_service.this.name }
output "uri" { value = google_cloud_run_v2_service.this.uri }
