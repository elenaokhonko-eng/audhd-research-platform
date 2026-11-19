# infra/terraform/modules/identity/tests/identity.tftest.hcl
mock_provider "google" {}

variables {
  project_id         = "example-dev"
  authorized_domains = ["dev.example.org"]
}

run "email_link_sign_in_is_on_and_passwords_are_not_required" {
  command = plan
  assert {
    condition     = google_identity_platform_config.this.sign_in[0].email[0].enabled == true
    error_message = "Email sign-in must be enabled."
  }
  assert {
    condition     = google_identity_platform_config.this.sign_in[0].email[0].password_required == false
    error_message = "Email-link sign-in needs password_required = false."
  }
  assert {
    condition     = google_identity_platform_config.this.sign_in[0].allow_duplicate_emails == false
    error_message = "One account per email."
  }
}

run "only_the_given_domains_are_authorised" {
  command = plan
  assert {
    condition     = toset(google_identity_platform_config.this.authorized_domains) == toset(["dev.example.org", "example-dev.firebaseapp.com"])
    error_message = "authorized_domains must be the input list plus the project's own sign-in handler domain, and nothing else (no localhost)."
  }
}

run "request_logging_is_off_and_clients_cannot_delete_accounts" {
  command = plan
  assert {
    condition     = google_identity_platform_config.this.monitoring[0].request_logging[0].enabled == false
    error_message = "Identity request logs would contain email addresses."
  }
  assert {
    condition     = google_identity_platform_config.this.client[0].permissions[0].disabled_user_deletion == true
    error_message = "Account deletion goes through the platform, not the browser."
  }
}
