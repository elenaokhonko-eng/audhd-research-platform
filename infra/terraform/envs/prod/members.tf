# Member sign-in: Identity Platform with email links. The web service reads its settings in main.tf.

module "identity" {
  source             = "../../modules/identity"
  project_id         = var.project_id
  authorized_domains = [var.domain, "www.${var.domain}"]
  depends_on         = [google_project_service.enabled]
}

# The contact key: contact_id is a keyed hash of an email address, computed inside Cloud KMS.
# Who may sign with it is bound in identities.tf.
module "contact_key" {
  source     = "../../modules/contact_key"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.enabled]
}

# Private buckets (no public access). Who reads and writes them is bound in identities.tf.
# library: the published files members download; versioned, kept for good.
module "library" {
  source     = "../../modules/private_bucket"
  name       = "${var.project_id}-library"
  project_id = var.project_id
  versioning = true
  depends_on = [google_project_service.enabled]
}

# library_staging: where a file waits between upload and publication; emptied after 7 days.
module "library_staging" {
  source            = "../../modules/private_bucket"
  name              = "${var.project_id}-library-staging"
  project_id        = var.project_id
  delete_after_days = 7
  force_destroy     = false
  depends_on        = [google_project_service.enabled]
}

# roster_inbox: where the owner drops a roster file for import; emptied after 7 days.
module "roster_inbox" {
  source            = "../../modules/private_bucket"
  name              = "${var.project_id}-roster-inbox"
  project_id        = var.project_id
  delete_after_days = 7
  force_destroy     = false
  depends_on        = [google_project_service.enabled]
}
