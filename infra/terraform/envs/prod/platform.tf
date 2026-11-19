# Stage 1 platform (S1.0): Firestore, the event bus, platform-api in its two HTTP modes and
# the selfcheck job. Identities and permissions are in identities.tf.

locals {
  platform_env = "prod"

  # Cloud Run's deterministic URL of platform-api. It is known before the service exists, so
  # the service can carry it as its own push audience without a dependency cycle, and the
  # push subscription can point at it. It equals module.platform_api.uri once created.
  platform_api_base_url = "https://platform-api-${data.google_project.this.number}.${var.region}.run.app"

  platform_common_env = {
    PLATFORM_ENV         = local.platform_env
    PLATFORM_GCP_PROJECT = var.project_id
  }
}

# ---------------------------------------------------------------- Firestore
resource "google_firestore_database" "default" {
  project                           = var.project_id
  name                              = "(default)"
  location_id                       = var.region
  type                              = "FIRESTORE_NATIVE"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"
  delete_protection_state           = "DELETE_PROTECTION_ENABLED"
  deletion_policy                   = "ABANDON"

  depends_on = [google_project_service.enabled]
}

# Record every read and write of member data (docs/architecture/08).
resource "google_project_iam_audit_config" "firestore_data_access" {
  project = var.project_id
  service = "datastore.googleapis.com"

  audit_log_config {
    log_type = "DATA_READ"
  }
  audit_log_config {
    log_type = "DATA_WRITE"
  }
}

# ---------------------------------------------------------------- event bus
module "event_bus" {
  source                     = "../../modules/event_bus"
  project_id                 = var.project_id
  push_endpoint_base         = local.platform_api_base_url
  push_service_account_email = google_service_account.pubsub_push.email
  push_audience              = local.platform_api_base_url
  depends_on                 = [google_project_service.enabled]
}

# ---------------------------------------------------------------- services
module "platform_api" {
  source                = "../../modules/platform_service"
  name                  = "platform-api"
  project_id            = var.project_id
  region                = var.region
  image                 = "us-docker.pkg.dev/cloudrun/container/hello"
  service_account_email = google_service_account.platform_api.email
  public                = false
  invokers              = local.platform_api_invokers
  deletion_protection   = true
  env = merge(local.platform_common_env, {
    PLATFORM_APP_MODE             = "api"
    PLATFORM_PUSH_AUDIENCE        = local.platform_api_base_url
    PLATFORM_PUSH_SERVICE_ACCOUNT = google_service_account.pubsub_push.email
  })
  depends_on = [google_project_service.enabled]
}

module "platform_hooks" {
  source                = "../../modules/platform_service"
  name                  = "platform-hooks"
  project_id            = var.project_id
  region                = var.region
  image                 = "us-docker.pkg.dev/cloudrun/container/hello"
  service_account_email = google_service_account.platform_hooks.email
  public                = true
  deletion_protection   = true
  env = merge(local.platform_common_env, {
    PLATFORM_APP_MODE = "hooks"
  })
  depends_on = [google_project_service.enabled]
}

# ---------------------------------------------------------------- jobs
resource "google_cloud_run_v2_job" "selfcheck" {
  project             = var.project_id
  name                = "platform-selfcheck"
  location            = var.region
  deletion_protection = true

  template {
    task_count = 1
    template {
      service_account = google_service_account.job_selfcheck.email
      max_retries     = 0
      timeout         = "300s"

      containers {
        # Placeholder until the first CI deploy replaces it.
        image   = "us-docker.pkg.dev/cloudrun/container/hello"
        command = ["platform-cli"]
        args    = ["job", "selfcheck"]

        dynamic "env" {
          for_each = local.platform_common_env
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

  depends_on = [google_project_service.enabled]
}

# ---------------------------------------------------------------- dead-letter alerts
# Any message held on a dead-letter subscription means an event was not delivered after five
# attempts. Nothing is discarded; the owner is told at once.
resource "google_monitoring_alert_policy" "dead_letter" {
  # Static names, so for_each is known at plan time; they match module.event_bus.dlq_hold_subscriptions.
  for_each     = toset(["platform-events-dlq-hold", "inbound-webhooks-dlq-hold"])
  display_name = "Undelivered messages on ${each.value}"
  combiner     = "OR"

  conditions {
    display_name = "${each.value} holds a message"
    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.type=\"pubsub_subscription\" AND resource.label.subscription_id=\"${each.value}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
  depends_on            = [module.event_bus]

  documentation {
    content   = "A message reached the dead-letter subscription ${each.value} after five failed deliveries. It is kept for 7 days. Inspect it with: gcloud pubsub subscriptions pull ${each.value} --limit=10"
    mime_type = "text/markdown"
  }
}
