# First uptime check (M13 starts here) and the budget guardrail.

resource "google_monitoring_notification_channel" "email" {
  display_name = "Owner email"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
  depends_on = [google_project_service.enabled]
}

locals {
  prod_host = var.check_custom_domain ? var.domain : trimprefix(module.web_prod.uri, "https://")
}

resource "google_monitoring_uptime_check_config" "web_prod" {
  display_name = "web-prod healthz"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/api/healthz"
    port         = 443
    use_ssl      = true
    validate_ssl = true
    accepted_response_status_codes {
      status_class = "STATUS_CLASS_2XX"
    }
  }

  content_matchers {
    content = "\"status\":\"ok\""
    matcher = "CONTAINS_STRING"
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = local.prod_host
    }
  }

  checker_type = "STATIC_IP_CHECKERS"
}

resource "google_monitoring_alert_policy" "web_prod_down" {
  display_name = "web-prod is down"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.web_prod.uptime_check_id}\" AND resource.type=\"uptime_url\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "300s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
      trigger {
        count = 1
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.id]

  documentation {
    content   = "audhdneurobiology.org health check failed from more than one location for 5 minutes. Runbook: docs/runbooks/stage-0.md, section 'Site is down'."
    mime_type = "text/markdown"
  }
}

resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account_id
  display_name    = "audhd platform monthly"

  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }

  amount {
    specified_amount {
      # currency_code omitted on purpose: the billing account's own currency is used.
      units = tostring(var.budget_amount)
    }
  }

  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.9 }
  threshold_rules { threshold_percent = 1.0 }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
    disable_default_iam_recipients   = false
  }

  depends_on = [google_project_service.enabled]
}
