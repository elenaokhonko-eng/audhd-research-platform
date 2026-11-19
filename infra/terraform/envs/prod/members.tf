# Member sign-in: Identity Platform with email links. The web service reads its settings in main.tf.

module "identity" {
  source             = "../../modules/identity"
  project_id         = var.project_id
  authorized_domains = [var.domain, "www.${var.domain}"]
  depends_on         = [google_project_service.enabled]
}
