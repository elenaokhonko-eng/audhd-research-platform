# Alerts of the launch (wave 2 of Stage 1). Each notifies the owner's email channel, and its text
# says in two sentences what happened and what to do first.
#
# Four marker alerts: the jobs write a log line holding alert=<marker> when a run fails, is stopped
# by the guard, is refused or reads a truncated file. One log-based metric and one policy each.
# Two alerts on Cloud Run's own metrics: a job execution that ended as failed (a crash, a missing
# key, a timeout: cases that write no marker), and 5xx answers of platform-api.
# One log-based alert on an email-shaped string in the logs of the platform's services and jobs.
#
# Filters are in the Logging query language. Its quoted strings take escape sequences, so a
# regular expression's "\." is written "\\." in the filter, which is "\\\\." in HCL.

locals {
  # Alert name => what to do first.
  markers = {
    "reconcile-failed"        = "The Stripe reconcile could not finish; nothing was changed. Run `platform-cli runs show` and read the job's log."
    "reconcile-guard-blocked" = "A run would have ended many memberships at once and was stopped; nothing was changed. Compare Stripe's subscriber count with the last good run before doing anything."
    "roster-refused"          = "The export import refused to run because there is no recent good reconcile. Run the reconcile first."
    "roster-truncated"        = "The export file is incomplete; nothing was applied. Export again from Substack and upload the new file."
  }

  # Entries written by 42-raise-test-alert.sh; accepted only where the switch is on (dev).
  test_log = "logName=\"projects/${var.project_id}/logs/platform-test\""

  cloud_run     = "resource.type=(\"cloud_run_revision\" OR \"cloud_run_job\")"
  marker_source = var.accept_test_log ? "(${local.cloud_run} OR ${local.test_log})" : "(${local.cloud_run})"

  # The platform's services and jobs.
  platform_resources = "(resource.type=\"cloud_run_revision\" AND resource.labels.service_name=(\"platform-api\" OR \"platform-hooks\")) OR resource.type=\"cloud_run_job\""
  address_source     = var.accept_test_log ? "(${local.platform_resources} OR ${local.test_log})" : "(${local.platform_resources})"

  # RE2, as Logging strings: an email shape, and the two excluded domains (also as subdomains).
  email_shape = "[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\\\\.[A-Za-z0-9-]+)*\\\\.[A-Za-z]{2,}"
  excluded    = ["[@.]example\\\\.org([^A-Za-z0-9-]|$)", "[@.]gserviceaccount\\\\.com([^A-Za-z0-9-]|$)"]

  # RE2 has no lookahead: a positive match on the shape and a negative match on each excluded
  # domain. The positive match also makes sure the field exists before the negative ones apply.
  address_match = join(" OR ", [
    for field in ["textPayload", "jsonPayload.message"] :
    "(${join(" AND ", concat(["${field}=~\"${local.email_shape}\""], [for e in local.excluded : "${field}!~\"${e}\""]))})"
  ])

  # These alerts have no "back to normal" signal; an open incident closes itself after 30 minutes.
  log_alert_auto_close = "1800s"
}

resource "google_logging_metric" "marker" {
  for_each = local.markers

  project     = var.project_id
  name        = "platform-alert-${each.key}"
  description = "Log lines holding alert=${replace(each.key, "-", "_")}."
  filter      = "${local.marker_source} AND (textPayload:\"alert=${replace(each.key, "-", "_")}\" OR jsonPayload.message:\"alert=${replace(each.key, "-", "_")}\")"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "marker" {
  for_each = local.markers

  project      = var.project_id
  display_name = "Platform alert: ${each.key}"
  combiner     = "OR"

  conditions {
    display_name = "A log line holds alert=${replace(each.key, "-", "_")}"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.marker[each.key].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = local.log_alert_auto_close
  }

  notification_channels = var.notification_channel_ids

  documentation {
    content   = each.value
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "job_failed" {
  project      = var.project_id
  display_name = "Platform alert: job-failed"
  combiner     = "OR"

  conditions {
    display_name = "An execution of stripe-reconcile or roster-import ended as failed"
    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/job/completed_execution_count\" AND resource.type=\"cloud_run_job\" AND metric.label.result=\"failed\" AND resource.label.job_name=one_of(\"stripe-reconcile\", \"roster-import\")"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.job_name"]
      }
      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = local.log_alert_auto_close
  }

  notification_channels = var.notification_channel_ids

  documentation {
    content   = "A job stopped without finishing. Open the job's log for its last execution. A blocked reconcile or a refused import also ends its job as failed: if a reconcile-guard-blocked or roster-refused email came at the same time, that email explains this one."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "api_errors" {
  project      = var.project_id
  display_name = "Platform alert: api-errors"
  combiner     = "OR"

  conditions {
    display_name = "platform-api answers 5xx to more than 5% of at least 20 requests over 10 minutes"
    condition_prometheus_query_language {
      # Over the last 10 minutes: (5xx answers / all answers) > 0.05, and only when there were
      # at least 20 answers, so that one error among three requests does not raise it.
      # "and on()" keeps the ratio only while the single-series count also exists.
      query               = <<-PROMQL
        (
          sum(increase(run_googleapis_com:request_count{monitored_resource="cloud_run_revision", service_name="platform-api", response_code_class="5xx"}[10m]))
          /
          sum(increase(run_googleapis_com:request_count{monitored_resource="cloud_run_revision", service_name="platform-api"}[10m]))
        ) > 0.05
        and on()
        sum(increase(run_googleapis_com:request_count{monitored_resource="cloud_run_revision", service_name="platform-api"}[10m])) >= 20
      PROMQL
      duration            = "0s"
      evaluation_interval = "60s"
    }
  }

  notification_channels = var.notification_channel_ids

  documentation {
    content   = "The member service is failing. Open its log for the last 15 minutes."
    mime_type = "text/markdown"
  }
}

resource "google_logging_metric" "address_in_logs" {
  project     = var.project_id
  name        = "platform-alert-address-in-logs"
  description = "Log lines of platform-api, platform-hooks or a job holding an email-shaped string outside example.org and gserviceaccount.com."
  filter      = "${local.address_source} AND (${local.address_match})"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_monitoring_alert_policy" "address_in_logs" {
  project      = var.project_id
  display_name = "Platform alert: address-in-logs"
  combiner     = "OR"

  conditions {
    display_name = "A log line holds an email-shaped string"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.address_in_logs.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = local.log_alert_auto_close
  }

  notification_channels = var.notification_channel_ids

  documentation {
    content   = "A log line contains what looks like an email address. This must not happen; find the line and tell the integrator. (A line that holds both an example.org or service-account address and a real one is not caught by this alert.)"
    mime_type = "text/markdown"
  }
}
