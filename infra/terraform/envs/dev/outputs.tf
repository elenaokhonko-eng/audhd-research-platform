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
  value       = module.web_dev.uri
}

output "contact_key_name" {
  description = "Version 1 of the contact key (PLATFORM_CONTACT_KEY of platform-api)"
  value       = module.contact_key.key_version_name
}

output "library_bucket" {
  value = module.library.name
}

output "library_staging_bucket" {
  value = module.library_staging.name
}

output "roster_inbox_bucket" {
  value = module.roster_inbox.name
}

output "auth_email_domain" {
  description = "The domain the sign-in email is sent from"
  value       = module.sending_domain.domain
}

output "stripe_key_secret_name" {
  description = "Secret Manager name of the Stripe read key; the owner adds its value from her terminal"
  value       = module.reconcile_job.secret_name
}

output "reconcile_job_name" {
  description = "Full resource name of the stripe-reconcile job (PLATFORM_RECONCILE_JOB of platform-api)"
  value       = module.reconcile_job.job_name
}

output "roster_import_job_name" {
  description = "Full resource name of the roster-import job"
  value       = module.roster_job.job_name
}
