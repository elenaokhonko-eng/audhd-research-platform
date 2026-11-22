# infra/terraform/modules/platform_alerts/tests/platform_alerts.tftest.hcl
mock_provider "google" {}

variables {
  project_id               = "example-dev"
  notification_channel_ids = ["projects/example-dev/notificationChannels/1"]
}

run "every_marker_has_a_metric_and_a_policy" {
  command = plan
  assert {
    condition     = toset(keys(google_logging_metric.marker)) == toset(["reconcile-failed", "reconcile-guard-blocked", "roster-refused", "roster-truncated"])
    error_message = "One metric per alert marker the code writes."
  }
  assert {
    condition     = alltrue([for name, m in google_logging_metric.marker : strcontains(m.filter, "alert=${replace(name, "-", "_")}")])
    error_message = "Each metric filters on its own marker."
  }
  assert {
    condition     = toset(keys(google_monitoring_alert_policy.marker)) == toset(keys(google_logging_metric.marker))
    error_message = "Each marker metric has an alert policy."
  }
}

run "the_test_log_is_accepted_only_where_it_is_switched_on" {
  command = plan
  variables {
    accept_test_log = true
  }
  assert {
    condition     = alltrue([for m in google_logging_metric.marker : strcontains(m.filter, "logs/platform-test")])
    error_message = "In dev the filters accept the test log."
  }
}

run "the_test_log_is_ignored_by_default" {
  command = plan
  assert {
    condition     = !anytrue([for m in google_logging_metric.marker : strcontains(m.filter, "logs/platform-test")])
    error_message = "Without the switch, a test entry raises nothing."
  }
}

run "every_policy_tells_the_owner_and_says_what_to_do" {
  command = plan
  assert {
    condition = alltrue([
      for p in concat(values(google_monitoring_alert_policy.marker), [google_monitoring_alert_policy.api_errors, google_monitoring_alert_policy.address_in_logs, google_monitoring_alert_policy.job_failed]) :
      p.notification_channels == tolist(["projects/example-dev/notificationChannels/1"]) && length(one(p.documentation).content) > 40
    ])
    error_message = "Every alert notifies the owner's channel and carries its instructions."
  }
}

run "the_address_alert_ignores_test_and_service_addresses" {
  command = plan
  assert {
    condition     = strcontains(google_logging_metric.address_in_logs.filter, "example\\\\.org") && strcontains(google_logging_metric.address_in_logs.filter, "gserviceaccount")
    error_message = "The filter must exclude example.org and service account addresses."
  }
}
