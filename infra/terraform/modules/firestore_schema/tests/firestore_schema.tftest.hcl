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
    condition     = length(google_firestore_index.this) == 6
    error_message = "Six composite indexes, as the plan lists them."
  }
}

run "each_index_has_exactly_its_fields_and_the_expiry_field_is_not_indexed" {
  command = plan
  assert {
    condition = toset([for i in google_firestore_index.this : join(",", concat([i.collection], [for f in i.fields : "${f.field_path}:${f.order}"]))]) == toset([
      "sync_runs,kind:ASCENDING,finished_at:DESCENDING",
      "sync_runs,kind:ASCENDING,state:ASCENDING,dry_run:ASCENDING,finished_at:DESCENDING",
      "sync_runs,kind:ASCENDING,dry_run:ASCENDING,finished_at:DESCENDING",
      "downloads,member_uid:ASCENDING,at:ASCENDING",
      "entitlements,status:ASCENDING,valid_until:ASCENDING",
      "audit_log,subject:ASCENDING,at:ASCENDING",
    ])
    error_message = "Each composite index has exactly the fields and orders of the plan's table."
  }
  assert {
    condition     = alltrue([for f in google_firestore_field.expires : length(f.index_config) == 1 && length(f.index_config[0].indexes) == 0])
    error_message = "expires_at is exempt from single-field indexing (an empty index_config)."
  }
}
