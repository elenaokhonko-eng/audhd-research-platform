# infra/terraform/modules/sending_domain/tests/sending_domain.tftest.hcl
mock_provider "cloudflare" {}

variables {
  enabled    = true
  zone_id    = "zone"
  zone_name  = "example.org"
  domain     = "dev.example.org"
  project_id = "example-dev"
}

run "exactly_one_spf_record_listing_every_include" {
  command = plan
  variables {
    spf_includes = ["_spf.firebasemail.com", "_spf.mx.cloudflare.net"]
  }
  assert {
    condition     = cloudflare_record.spf[0].content == "v=spf1 include:_spf.firebasemail.com include:_spf.mx.cloudflare.net ~all"
    error_message = "One SPF record must carry every include, in order."
  }
  assert {
    condition     = length(cloudflare_record.spf) == 1
    error_message = "A domain may have only one v=spf1 record."
  }
}

run "default_dkim_targets_follow_the_documented_pattern" {
  command = plan
  assert {
    condition     = cloudflare_record.dkim["firebase1"].content == "mail-dev-example-org.dkim1._domainkey.firebasemail.com"
    error_message = "Selector firebase1 must point at the dkim1 host for this domain."
  }
  assert {
    condition     = cloudflare_record.dkim["firebase2"].content == "mail-dev-example-org.dkim2._domainkey.firebasemail.com"
    error_message = "Selector firebase2 must point at the dkim2 host for this domain."
  }
  assert {
    condition     = cloudflare_record.dkim["firebase1"].proxied == false
    error_message = "Mail records are DNS-only."
  }
}

run "dmarc_starts_at_none_and_adds_reports_only_when_asked" {
  command = plan
  assert {
    condition     = cloudflare_record.dmarc[0].content == "v=DMARC1; p=none"
    error_message = "Default DMARC record."
  }
}

run "dmarc_with_a_report_address" {
  command = plan
  variables {
    dmarc_report_address = "reports@example.org"
  }
  assert {
    condition     = cloudflare_record.dmarc[0].content == "v=DMARC1; p=none; rua=mailto:reports@example.org"
    error_message = "DMARC record with a report address."
  }
}

run "disabled_creates_nothing" {
  command = plan
  variables {
    enabled = false
  }
  assert {
    condition     = length(cloudflare_record.spf) == 0 && length(cloudflare_record.dkim) == 0 && length(cloudflare_record.dmarc) == 0
    error_message = "No DNS records when DNS is not managed here."
  }
}
