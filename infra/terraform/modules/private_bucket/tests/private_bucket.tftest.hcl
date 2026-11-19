# infra/terraform/modules/private_bucket/tests/private_bucket.tftest.hcl
mock_provider "google" {}

variables {
  name       = "example-dev-library"
  project_id = "example-dev"
}

run "a_bucket_is_never_public" {
  command = plan
  assert {
    condition     = google_storage_bucket.this.public_access_prevention == "enforced"
    error_message = "Public access prevention must be enforced."
  }
  assert {
    condition     = google_storage_bucket.this.uniform_bucket_level_access == true
    error_message = "Uniform bucket-level access must be on."
  }
  assert {
    condition     = google_storage_bucket.this.location == "ASIA-SOUTHEAST1"
    error_message = "Buckets live in asia-southeast1."
  }
}

run "no_lifecycle_rule_unless_asked" {
  command = plan
  assert {
    condition     = length(google_storage_bucket.this.lifecycle_rule) == 0
    error_message = "The library keeps its files."
  }
}

run "delete_after_days_adds_exactly_one_delete_rule" {
  command = plan
  variables {
    delete_after_days = 7
  }
  assert {
    condition     = length(google_storage_bucket.this.lifecycle_rule) == 1
    error_message = "Expected one lifecycle rule."
  }
  assert {
    condition     = one(google_storage_bucket.this.lifecycle_rule[0].condition).age == 7
    error_message = "Objects are deleted after 7 days."
  }
  assert {
    condition     = one(google_storage_bucket.this.lifecycle_rule[0].action).type == "Delete"
    error_message = "The rule must delete."
  }
}

run "versioning_follows_the_input" {
  command = plan
  variables {
    versioning = true
  }
  assert {
    condition     = google_storage_bucket.this.versioning[0].enabled == true
    error_message = "Versioning must be on when asked."
  }
}
