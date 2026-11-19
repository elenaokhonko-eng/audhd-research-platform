# Dev root: its own project (audhd-neurobiology-dev), applied after prod. APIs, image
# registry, the dev website and its host dev.<domain>. No budget: the one budget is declared in
# envs/prod/monitoring.tf and its filter covers the prod project only, so dev spending is not
# watched by it. No apex records. platform.tf adds platform-api, the event bus
# and Firestore; every service account and permission is in identities.tf.

locals {
  services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "secretmanager.googleapis.com",
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
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
module "web_dev" {
  source          = "../../modules/web_service"
  name            = "web-dev"
  region          = var.region
  site_env        = "dev"
  max_instances   = 2
  service_account = google_service_account.web_runtime.email
  depends_on      = [google_project_service.enabled]
}

# ---------------------------------------------------------------- dev.<domain>
# Same pattern as envs/prod/domain.tf (ADR 0003), for the dev host only. The record is
# DNS-only (grey cloud): Google must see its own IPs to issue the certificate.
resource "google_cloud_run_domain_mapping" "dev" {
  count    = var.map_custom_domains ? 1 : 0
  location = var.region
  name     = "dev.${var.domain}"

  metadata {
    namespace = data.google_project.this.project_id
  }

  spec {
    route_name = module.web_dev.name
  }
}

resource "cloudflare_record" "dev" {
  count   = var.manage_cloudflare_dns && var.map_custom_domains ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = "dev"
  type    = "CNAME"
  content = "ghs.googlehosted.com"
  proxied = false
  ttl     = 300
  comment = "Cloud Run domain mapping (Terraform)"
}
