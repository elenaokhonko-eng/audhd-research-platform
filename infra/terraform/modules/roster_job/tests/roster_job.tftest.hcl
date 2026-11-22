# infra/terraform/modules/roster_job/tests/roster_job.tftest.hcl
mock_provider "google" {}

variables {
  project_id                = "example-dev"
  region                    = "asia-southeast1"
  env                       = { PLATFORM_ENV = "dev" }
  job_service_account_email = "job-substack@example-dev.iam.gserviceaccount.com"
  roster_inbox_bucket       = "example-dev-roster-inbox"
  owner_member              = "user:owner@example.org"
  runner_role_id            = "projects/example-dev/roles/platformJobRunner"
  overrides_role            = "roles/example.overrides"
}

run "only_the_owner_starts_the_import" {
  command = plan
  assert {
    condition     = google_cloud_run_v2_job_iam_binding.runners.members == toset(["user:owner@example.org"]) && google_cloud_run_v2_job_iam_binding.overrides.members == toset(["user:owner@example.org"])
    error_message = "Only the owner may start the roster import, with or without changed settings."
  }
}

run "the_job_reads_the_inbox_and_nothing_else" {
  command = plan
  assert {
    condition     = google_storage_bucket_iam_member.reads_inbox.role == "roles/storage.objectViewer" && google_storage_bucket_iam_member.reads_inbox.bucket == "example-dev-roster-inbox"
    error_message = "The import job reads the roster inbox."
  }
  assert {
    condition     = google_cloud_run_v2_job.this.template[0].template[0].containers[0].args == tolist(["job", "roster-import"])
    error_message = "The job must run platform-cli job roster-import."
  }
}
