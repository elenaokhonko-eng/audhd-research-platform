output "index_ids" {
  description = "Ids of the composite indexes, by name"
  value       = { for name, index in google_firestore_index.this : name => index.id }
}

output "ttl_collections" {
  description = "Collections whose records expire on their expires_at field"
  value       = sort(keys(google_firestore_field.expires))
}
