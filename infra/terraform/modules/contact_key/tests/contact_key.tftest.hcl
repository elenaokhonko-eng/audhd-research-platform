# infra/terraform/modules/contact_key/tests/contact_key.tftest.hcl
mock_provider "google" {}

variables {
  project_id = "example-dev"
  region     = "asia-southeast1"
}

run "the_key_is_a_mac_key_that_never_rotates" {
  command = plan
  assert {
    condition     = google_kms_crypto_key.contact_id.purpose == "MAC"
    error_message = "contact_id is derived with a keyed hash."
  }
  assert {
    condition     = google_kms_crypto_key.contact_id.version_template[0].algorithm == "HMAC_SHA256"
    error_message = "Algorithm must be HMAC_SHA256."
  }
  assert {
    condition     = google_kms_crypto_key.contact_id.rotation_period == null
    error_message = "Rotation would change every contact id."
  }
  assert {
    condition     = google_kms_key_ring.platform.location == "asia-southeast1"
    error_message = "Key ring must be regional."
  }
}

run "the_version_name_points_at_version_one" {
  command = plan # never apply: the clean-up after an apply would meet prevent_destroy
  override_resource {
    target          = google_kms_crypto_key.contact_id
    override_during = plan
    values          = { id = "projects/example-dev/locations/asia-southeast1/keyRings/platform/cryptoKeys/contact-id" }
  }
  assert {
    condition     = endswith(output.key_version_name, "/cryptoKeyVersions/1")
    error_message = "Callers sign with version 1."
  }
}
