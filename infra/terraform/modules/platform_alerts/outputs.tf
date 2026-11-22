output "marker_metric_names" {
  description = "Log-based metric of each marker alert, by alert name."
  value       = { for name, m in google_logging_metric.marker : name => m.name }
}

output "alert_policy_ids" {
  description = "Every alert policy of the module, by alert name."
  value = merge(
    { for name, p in google_monitoring_alert_policy.marker : name => p.id },
    {
      "job-failed"      = google_monitoring_alert_policy.job_failed.id
      "api-errors"      = google_monitoring_alert_policy.api_errors.id
      "address-in-logs" = google_monitoring_alert_policy.address_in_logs.id
    },
  )
}
