# Wave 2 of Stage 1: the two jobs of the launch. stripe-reconcile reads Stripe with a
# restricted, read-only key and runs on a schedule that is created paused; roster-import reads
# the owner's roster export and is started by the owner only. Their identities, the runner role
# and their shared grants are in identities.tf; each module holds the bindings on its own job,
# secret and bucket.

locals {
  # Dev only: a sandbox subscription with metadata test_channel=substack stands in for one
  # created by Substack. Empty in prod, where Settings would refuse it.
  platform_job_dev_env = {
    for name, value in { PLATFORM_STRIPE_TEST_CHANNEL_METADATA = "true" } : name => value
    if local.platform_env == "dev"
  }

  # What both jobs read.
  platform_job_env = merge(local.platform_common_env, local.platform_job_dev_env, {
    PLATFORM_CONTACT_KEY                 = module.contact_key.key_version_name
    PLATFORM_STRIPE_SUBSTACK_APPLICATION = var.stripe_substack_application
    PLATFORM_SUBSTACK_GRANT_MONTH        = var.substack_grant_month
    PLATFORM_SUBSTACK_GRANT_YEAR         = var.substack_grant_year
  })

  # Ruling 2 of the wave-2 plan: the narrowest predefined role with run.jobs.runWithOverrides.
  job_overrides_role = "roles/run.jobsExecutorWithOverrides"
}

module "reconcile_job" {
  source                          = "../../modules/reconcile_job"
  project_id                      = var.project_id
  region                          = var.region
  env                             = local.platform_job_env
  job_service_account_email       = google_service_account.job_stripe.email
  api_service_account_email       = google_service_account.platform_api.email
  owner_member                    = var.owner_member
  runner_role_id                  = google_project_iam_custom_role.platform_job_runner.id
  overrides_role                  = local.job_overrides_role
  schedule                        = var.reconcile_schedule
  schedule_enabled                = var.reconcile_schedule_enabled
  scheduler_service_account_email = google_service_account.scheduler.email
  depends_on                      = [google_project_service.enabled]
}

module "roster_job" {
  source     = "../../modules/roster_job"
  project_id = var.project_id
  region     = var.region
  env = merge(local.platform_job_env, {
    PLATFORM_ROSTER_INBOX_BUCKET = module.roster_inbox.name
  })
  job_service_account_email = google_service_account.job_substack.email
  roster_inbox_bucket       = module.roster_inbox.name
  owner_member              = var.owner_member
  runner_role_id            = google_project_iam_custom_role.platform_job_runner.id
  overrides_role            = local.job_overrides_role
  depends_on                = [google_project_service.enabled]
}
