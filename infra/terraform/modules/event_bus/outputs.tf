output "platform_events_topic" {
  description = "Name of platform.events"
  value       = google_pubsub_topic.platform_events.name
}

output "platform_events_dlq_topic" {
  value = google_pubsub_topic.platform_events_dlq.name
}

output "inbound_webhooks_topic" {
  value = google_pubsub_topic.inbound_webhooks.name
}

output "inbound_webhooks_dlq_topic" {
  value = google_pubsub_topic.inbound_webhooks_dlq.name
}

output "push_subscription" {
  description = "Name of the push subscription platform-events-to-api"
  value       = google_pubsub_subscription.platform_events_to_api.name
}

output "dlq_hold_subscriptions" {
  description = "Names of the dead-letter hold subscriptions"
  value       = [for s in google_pubsub_subscription.dlq_hold : s.name]
}
