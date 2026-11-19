output "key_id" {
  description = "Id of the contact key"
  value       = google_kms_crypto_key.contact_id.id
}

output "key_version_name" {
  description = "Version 1 of the contact key, the one callers sign with"
  value       = "${google_kms_crypto_key.contact_id.id}/cryptoKeyVersions/1"
}
