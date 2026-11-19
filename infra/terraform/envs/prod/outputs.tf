output "web_prod_url" {
  value = module.web_prod.uri
}

output "platform_api_url" {
  description = "platform-api (private); also the audience of identity tokens sent to it"
  value       = module.platform_api.uri
}

output "platform_hooks_url" {
  description = "platform-hooks (public webhook receiver)"
  value       = module.platform_hooks.uri
}

output "artifact_registry" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.platform.repository_id}"
}

output "wif_provider" {
  description = "GitHub repo variable WIF_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "GitHub repo variable DEPLOYER_SA"
  value       = google_service_account.deployer.email
}

output "web_runtime_service_account" {
  value = google_service_account.web_runtime.email
}

output "domain_records" {
  description = "DNS records Google expects for each mapped host (compare with Cloudflare)"
  value       = { for k, m in google_cloud_run_domain_mapping.this : m.name => try(m.status[0].resource_records, []) }
}

output "identity_api_key" {
  description = "Browser API key for sign-in (public value; sensitive only to keep it out of logs)"
  value       = module.identity.api_key
  sensitive   = true
}

output "identity_auth_domain" {
  value = module.identity.auth_domain
}

output "web_url" {
  description = "The web service"
  value       = module.web_prod.uri
}
