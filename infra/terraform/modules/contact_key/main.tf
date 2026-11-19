# The contact key: a Cloud KMS HMAC key. contact_id is a keyed hash of a person's email address,
# computed by asking KMS to sign; the key material never leaves KMS. Rotating or destroying the
# key would change every contact id, so there is no rotation period and the key cannot be
# destroyed by Terraform. Who may sign with it is bound in each root's identities.tf.

resource "google_project_service" "kms" {
  project            = var.project_id
  service            = "cloudkms.googleapis.com"
  disable_on_destroy = false
}

resource "google_kms_key_ring" "platform" {
  project  = var.project_id
  name     = "platform"
  location = var.region

  depends_on = [google_project_service.kms]
}

resource "google_kms_crypto_key" "contact_id" {
  name     = "contact-id"
  key_ring = google_kms_key_ring.platform.id
  purpose  = "MAC"

  version_template {
    algorithm        = "HMAC_SHA256"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}
