output "job_name" {
  description = "Full resource name of the stripe-reconcile job (PLATFORM_RECONCILE_JOB of platform-api)"
  value       = google_cloud_run_v2_job.this.id
}

output "secret_name" {
  description = "Secret Manager name of the Stripe read key (the owner adds its value from her terminal)"
  value       = google_secret_manager_secret.stripe.id
}
