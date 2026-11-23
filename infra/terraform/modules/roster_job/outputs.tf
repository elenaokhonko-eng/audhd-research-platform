output "job_name" {
  description = "Full resource name of the roster-import job"
  value       = google_cloud_run_v2_job.this.id
}
