# Production root. Stage 0 foundation: APIs, image registry, the production website, custom
# domain, DNS, uptime check, budget. Stage 1 adds platform.tf (platform-api, event bus, Firestore).
# Every service account and permission is in identities.tf.

locals {
  services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "secretmanager.googleapis.com",
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
    "cloudscheduler.googleapis.com",
  ]
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_service" "enabled" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------- images
resource "google_artifact_registry_repository" "platform" {
  location      = var.region
  repository_id = "platform"
  format        = "DOCKER"
  description   = "Container images for every platform service"

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 15
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.enabled]
}

# ---------------------------------------------------------------- web (M1)
# The preview site web-dev and its host dev.<domain> live in the dev project (envs/dev).
module "web_prod" {
  source          = "../../modules/web_service"
  name            = "web-prod"
  region          = var.region
  site_env        = "prod"
  max_instances   = 10
  service_account = google_service_account.web_runtime.email
  env = {
    IDENTITY_API_KEY     = nonsensitive(module.identity.api_key) # public browser value
    IDENTITY_AUTH_DOMAIN = module.identity.auth_domain
    PLATFORM_API_URL     = module.platform_api.uri
    SITE_ORIGIN          = "https://${var.domain}"
    SIGNIN_SENDER_HINT   = var.signin_sender_hint
  }
  depends_on = [google_project_service.enabled]
}
