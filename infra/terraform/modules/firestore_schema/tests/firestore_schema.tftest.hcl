mock_provider "google" {}

variables {
  project_id = "example-dev"
}

run "records_with_a_lifetime_expire_by_themselves" {
  command = plan
  assert {
    condition     = toset(keys(google_firestore_field.expires)) == toset(["downloads", "support_requests", "audit_log", "rate_limits"])
    error_message = "Exactly these collections have a time-to-live policy; the privacy notice names their lifetimes."
  }
  assert {
    condition     = alltrue([for f in google_firestore_field.expires : f.field == "expires_at" && length(f.ttl_config) == 1])
    error_message = "The policy is on the field expires_at."
  }
}

run "the_queries_have_their_indexes" {
  command = plan
  assert {
    condition     = toset([for i in google_firestore_index.this : i.collection]) == toset(["sync_runs", "downloads", "entitlements", "audit_log"])
    error_message = "Composite indexes exist for sync_runs, downloads, entitlements and audit_log."
  }
  assert {
    condition     = length(google_firestore_index.this) == 5
    error_message = "Five composite indexes, as the plan lists them."
  }
}
