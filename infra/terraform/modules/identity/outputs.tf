output "api_key" {
  description = "Browser API key for Identity Platform (a public value, restricted by API and referrer)"
  value       = google_apikeys_key.browser.key_string
  sensitive   = true
}

output "auth_domain" {
  description = "Domain that hosts the sign-in handler"
  value       = local.auth_domain
}
