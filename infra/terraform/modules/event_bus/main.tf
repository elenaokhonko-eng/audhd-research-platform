# The event bus (docs/architecture/09-events-and-data-model.md): topics, the push
# subscription that delivers platform events to platform-api, and dead-letter topics with a
# pull subscription each, so a message that cannot be delivered is kept, never discarded.
# Who may publish or subscribe is declared in the root's identities.tf, not here.

locals {
  retention = "604800s" # 7 days
}

resource "google_pubsub_topic" "platform_events" {
  project = var.project_id
  name    = "platform.events"
}

resource "google_pubsub_topic" "platform_events_dlq" {
  project = var.project_id
  name    = "platform.events.dlq"
}

resource "google_pubsub_topic" "inbound_webhooks" {
  project = var.project_id
  name    = "inbound.webhooks"
}

resource "google_pubsub_topic" "inbound_webhooks_dlq" {
  project = var.project_id
  name    = "inbound.webhooks.dlq"
}

# platform.events -> platform-api. Pub/Sub signs each push with an OIDC token for
# pubsub-push; platform-api accepts only that identity and audience.
resource "google_pubsub_subscription" "platform_events_to_api" {
  project = var.project_id
  name    = "platform-events-to-api"
  topic   = google_pubsub_topic.platform_events.id

  ack_deadline_seconds       = 60
  message_retention_duration = local.retention

  push_config {
    push_endpoint = "${var.push_endpoint_base}/internal/pubsub/platform-events"
    oidc_token {
      service_account_email = var.push_service_account_email
      audience              = var.push_audience
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.platform_events_dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  expiration_policy {
    ttl = "" # never expires for inactivity
  }
}

# One pull subscription per dead-letter topic. Nothing reads them automatically: they hold
# messages for the owner to inspect, and an alert fires as soon as one arrives.
resource "google_pubsub_subscription" "dlq_hold" {
  for_each = {
    "platform-events-dlq-hold"  = google_pubsub_topic.platform_events_dlq.id
    "inbound-webhooks-dlq-hold" = google_pubsub_topic.inbound_webhooks_dlq.id
  }
  project = var.project_id
  name    = each.key
  topic   = each.value

  ack_deadline_seconds       = 60
  message_retention_duration = local.retention

  expiration_policy {
    ttl = ""
  }
}
