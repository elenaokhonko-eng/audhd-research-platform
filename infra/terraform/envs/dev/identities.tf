# Permissions manifest of the dev project (docs/architecture/08-security-identities-and-org.md §3).
# Every service account and every IAM binding of this root is in this file, and nothing else
# is: reviewing who can do what is reading this file. No key file exists for any of them.
#
# One binding is declared through a module input rather than a resource here: who may invoke
# the private platform-api service. The list is local.platform_api_invokers below; the module
# in platform.tf turns it into roles/run.invoker bindings.

locals {
  # Pub/Sub's own service agent. It moves undeliverable messages to the dead-letter topics.
  pubsub_service_agent = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"

  # Callers of platform-api: the website (forwarding a member's session) and Pub/Sub pushes.
  platform_api_invokers = [
    google_service_account.web_runtime.email,
    google_service_account.pubsub_push.email,
  ]
}

# ---------------------------------------------------------------- service accounts
# Runtime identity of the website. Its only permission is to call platform-api (above).
# It reads no data store and no secret.
resource "google_service_account" "web_runtime" {
  account_id   = "web-runtime"
  display_name = "Website runtime (calls platform-api only)"
  depends_on   = [google_project_service.enabled]
}

# Identity GitHub Actions borrows through Workload Identity Federation. No key file exists.
resource "google_service_account" "deployer" {
  account_id   = "github-deployer"
  display_name = "GitHub Actions deployer"
  depends_on   = [google_project_service.enabled]
}

resource "google_service_account" "platform_api" {
  account_id   = "platform-api"
  display_name = "platform-api service"
  depends_on   = [google_project_service.enabled]
}

resource "google_service_account" "platform_hooks" {
  account_id   = "platform-hooks"
  display_name = "platform-hooks webhook receiver (public)"
  depends_on   = [google_project_service.enabled]
}

resource "google_service_account" "job_selfcheck" {
  account_id   = "job-selfcheck"
  display_name = "platform-selfcheck job"
  depends_on   = [google_project_service.enabled]
}

resource "google_service_account" "pubsub_push" {
  account_id   = "pubsub-push"
  display_name = "Pub/Sub push to platform-api"
  depends_on   = [google_project_service.enabled]
}

# ---------------------------------------------------------------- platform-api
resource "google_project_iam_member" "platform_api_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.platform_api.email}"
}

resource "google_pubsub_topic_iam_member" "platform_api_publishes_events" {
  project = var.project_id
  topic   = module.event_bus.platform_events_topic
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.platform_api.email}"
}

# The contact key signs only: a custom role with the one permission contact_id needs. No one
# can read the key, export it or manage its versions through this binding.
resource "google_project_iam_custom_role" "platform_contact_key_user" {
  project     = var.project_id
  role_id     = "platformContactKeyUser"
  title       = "Contact key signer"
  description = "Sign with the contact key to derive contact_id. Nothing else."
  permissions = ["cloudkms.cryptoKeyVersions.useToSign"]
}

resource "google_kms_crypto_key_iam_member" "platform_api_signs_contact_id" {
  crypto_key_id = module.contact_key.key_id
  role          = google_project_iam_custom_role.platform_contact_key_user.id
  member        = "serviceAccount:${google_service_account.platform_api.email}"
}

# ---------------------------------------------------------------- platform-hooks
# Publishes to the inbound topic only. It reads nothing.
resource "google_pubsub_topic_iam_member" "platform_hooks_publishes_inbound" {
  project = var.project_id
  topic   = module.event_bus.inbound_webhooks_topic
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.platform_hooks.email}"
}

# ---------------------------------------------------------------- job-selfcheck
resource "google_pubsub_topic_iam_member" "job_selfcheck_publishes_events" {
  project = var.project_id
  topic   = module.event_bus.platform_events_topic
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.job_selfcheck.email}"
}

# ---------------------------------------------------------------- Pub/Sub service agent
# Dead-lettering needs the agent to publish to the dead-letter topic and to acknowledge the
# message on the subscription it came from.
resource "google_pubsub_topic_iam_member" "pubsub_agent_publishes_dlq" {
  for_each = {
    platform_events  = module.event_bus.platform_events_dlq_topic
    inbound_webhooks = module.event_bus.inbound_webhooks_dlq_topic
  }
  project = var.project_id
  topic   = each.value
  role    = "roles/pubsub.publisher"
  member  = local.pubsub_service_agent
}

resource "google_pubsub_subscription_iam_member" "pubsub_agent_subscribes_push" {
  project      = var.project_id
  subscription = module.event_bus.push_subscription
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_service_agent
}

# ---------------------------------------------------------------- github-deployer
resource "google_project_iam_member" "deployer_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_artifact_registry_repository_iam_member" "deployer_push" {
  location   = google_artifact_registry_repository.platform.location
  repository = google_artifact_registry_repository.platform.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deployer.email}"
}

# The deployer may attach the runtime identities to a revision, and nothing else.
resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.web_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "deployer_acts_as_platform" {
  for_each = {
    platform_api   = google_service_account.platform_api.name
    platform_hooks = google_service_account.platform_hooks.name
    job_selfcheck  = google_service_account.job_selfcheck.name
  }
  service_account_id = each.value
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# ---------------------------------------------------------------- GitHub workload identity
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  # environment is present only when the GitHub job names an environment, so it is mapped
  # with a fallback rather than read directly (as in envs/prod/identities.tf).
  attribute_mapping = {
    "google.subject"        = "assertion.sub"
    "attribute.repository"  = "assertion.repository"
    "attribute.ref"         = "assertion.ref"
    "attribute.environment" = "has(assertion.environment) ? assertion.environment : \"none\""
  }
  # Only this one repository can exchange a GitHub token for a Google token.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# The dev deployer can be borrowed only by a workflow of this repository (provider condition
# above) running a job in the GitHub environment "dev". A job without that environment, such
# as a pull request check, gets no Google token for this project. Production is restricted
# further in envs/prod/identities.tf.
resource "google_service_account_iam_member" "github_impersonates_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.environment/dev"
}

# ---------------------------------------------------------------- buckets
# platform-api reads the library and copies published files into it, and reads what waits in
# staging. The import job's access to roster_inbox is bound in Wave 2.
resource "google_storage_bucket_iam_member" "platform_api_reads" {
  for_each = {
    library         = module.library.name
    library_staging = module.library_staging.name
  }
  bucket = each.value
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.platform_api.email}"
}

resource "google_storage_bucket_iam_member" "platform_api_writes_library" {
  bucket = module.library.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.platform_api.email}"
}

# The owner may add files to the two inbox buckets (not read or delete them).
resource "google_storage_bucket_iam_member" "owner_writes_inboxes" {
  for_each = {
    library_staging = module.library_staging.name
    roster_inbox    = module.roster_inbox.name
  }
  bucket = each.value
  role   = "roles/storage.objectCreator"
  member = var.owner_member
}

# platform-api signs download links as itself, without a key file.
resource "google_service_account_iam_member" "platform_api_signs_as_itself" {
  service_account_id = google_service_account.platform_api.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.platform_api.email}"
}
