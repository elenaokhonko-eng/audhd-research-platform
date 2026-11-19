output "web_dev_url" {
  value = module.web_dev.uri
}

output "platform_api_url" {
  description = "platform-api (private), its Cloud Run URL. Pub/Sub push tokens use the deterministic URL (local.platform_api_base_url) as their audience, not this one"
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
  description = "GitHub environment variable WIF_PROVIDER (environment dev)"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_service_account" {
  description = "GitHub environment variable DEPLOYER_SA (environment dev)"
  value       = google_service_account.deployer.email
}

output "web_runtime_service_account" {
  value = google_service_account.web_runtime.email
}

output "domain_records" {
  description = "DNS records Google expects for dev.<domain> (compare with Cloudflare)"
  value       = { for m in google_cloud_run_domain_mapping.dev : m.name => try(m.status[0].resource_records, []) }
}
