# infra/terraform/modules/reconcile_job/tests/reconcile_job.tftest.hcl
mock_provider "google" {}

variables {
  project_id                      = "example-dev"
  region                          = "asia-southeast1"
  env                             = { PLATFORM_ENV = "dev" }
  job_service_account_email       = "job-stripe@example-dev.iam.gserviceaccount.com"
  api_service_account_email       = "platform-api@example-dev.iam.gserviceaccount.com"
  owner_member                    = "user:owner@example.org"
  runner_role_id                  = "projects/example-dev/roles/platformJobRunner"
  overrides_role                  = "roles/example.overrides"
  scheduler_service_account_email = "scheduler@example-dev.iam.gserviceaccount.com"
}

run "only_the_job_reads_the_key" {
  command = plan
  assert {
    condition     = google_secret_manager_secret_iam_binding.readers.role == "roles/secretmanager.secretAccessor"
    error_message = "The binding must be the accessor role."
  }
  assert {
    condition     = google_secret_manager_secret_iam_binding.readers.members == toset(["serviceAccount:job-stripe@example-dev.iam.gserviceaccount.com"])
    error_message = "Only the reconcile job's identity may read the Stripe key."
  }
}

run "the_secret_stays_in_the_region" {
  command = plan
  assert {
    condition     = one(one(google_secret_manager_secret.stripe.replication).user_managed).replicas[0].location == "asia-southeast1"
    error_message = "The secret must be stored in the platform's region."
  }
}

run "who_may_start_the_job_and_who_may_change_a_run" {
  command = plan
  assert {
    condition = google_cloud_run_v2_job_iam_binding.runners.role == "projects/example-dev/roles/platformJobRunner" && google_cloud_run_v2_job_iam_binding.runners.members == toset([
      "serviceAccount:platform-api@example-dev.iam.gserviceaccount.com",
      "user:owner@example.org",
      "serviceAccount:scheduler@example-dev.iam.gserviceaccount.com",
    ])
    error_message = "Exactly the API, the owner and the scheduler may start the reconcile."
  }
  assert {
    condition     = google_cloud_run_v2_job_iam_binding.overrides.role == "roles/example.overrides" && google_cloud_run_v2_job_iam_binding.overrides.members == toset(["user:owner@example.org"])
    error_message = "Only the owner may start a run with changed settings."
  }
}

run "the_job_runs_the_right_command_as_its_own_identity" {
  command = plan
  assert {
    condition     = google_cloud_run_v2_job.this.template[0].template[0].containers[0].args == tolist(["job", "stripe-reconcile"])
    error_message = "The job must run platform-cli job stripe-reconcile."
  }
  assert {
    condition     = google_cloud_run_v2_job.this.template[0].template[0].max_retries == 0
    error_message = "A failed reconcile is not retried blindly; the next schedule runs it."
  }
  assert {
    condition     = contains([for e in google_cloud_run_v2_job.this.template[0].template[0].containers[0].env : "${e.name}=${e.value}"], "PLATFORM_STRIPE_KEY_SECRET=projects/example-dev/secrets/stripe-read-key/versions/latest")
    error_message = "The job needs the name of the secret."
  }
}

run "the_schedule_is_a_variable_and_starts_paused" {
  command = plan
  variables {
    schedule = "*/10 * * * *"
  }
  assert {
    condition     = google_cloud_scheduler_job.reconcile.schedule == "*/10 * * * *" && google_cloud_scheduler_job.reconcile.time_zone == "Etc/UTC"
    error_message = "The schedule must come from the variable, in UTC."
  }
  assert {
    condition     = google_cloud_scheduler_job.reconcile.paused == true
    error_message = "The schedule is paused until the owner switches it on."
  }
}

run "a_schedule_faster_than_the_job_is_refused" {
  command = plan
  variables {
    schedule = "*/5 * * * *"
  }
  expect_failures = [var.schedule]
}
