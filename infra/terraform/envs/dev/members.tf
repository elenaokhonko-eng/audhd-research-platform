# Member sign-in: Identity Platform with email links. The web service reads its settings in main.tf.

module "identity" {
  source             = "../../modules/identity"
  project_id         = var.project_id
  authorized_domains = ["dev.${var.domain}"]
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
