# Identity Platform: email-link sign-in (no passwords) for members. The browser API key is a
# public value, restricted to the Identity Toolkit API and to the site's own hosts.

resource "google_project_service" "identitytoolkit" {
  project            = var.project_id
  service            = "identitytoolkit.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "apikeys" {
  project            = var.project_id
  service            = "apikeys.googleapis.com"
  disable_on_destroy = false
}

locals {
  # The project's own domain hosts the sign-in handler (Google sign-in). localhost is left out
  # on purpose.
  auth_domain = "${var.project_id}.firebaseapp.com"
}

resource "google_identity_platform_config" "this" {
  project                    = var.project_id
  authorized_domains         = concat(var.authorized_domains, [local.auth_domain])
  autodelete_anonymous_users = true

  sign_in {
    allow_duplicate_emails = false

    email {
      enabled           = true
      password_required = false
    }
  }

  multi_tenant {
    allow_tenants = false
  }

  client {
    permissions {
      disabled_user_signup   = false
      disabled_user_deletion = true
    }
  }

  # Request logs would contain email addresses.
  monitoring {
    request_logging {
      enabled = false
    }
  }

  depends_on = [google_project_service.identitytoolkit]
}

resource "google_apikeys_key" "browser" {
  project      = var.project_id
  name         = "identity-browser"
  display_name = "Identity Platform browser key"

  restrictions {
    api_targets {
      service = "identitytoolkit.googleapis.com"
    }
    api_targets {
      service = "securetoken.googleapis.com"
    }
    browser_key_restrictions {
      allowed_referrers = concat(
        [for d in var.authorized_domains : "https://${d}/*"],
        ["https://${local.auth_domain}/*"],
      )
    }
  }

  depends_on = [google_project_service.apikeys, google_identity_platform_config.this]
}
