# DNS records that let Firebase Authentication send the sign-in email from our own domain.
# One SPF record (a domain may carry only one v=spf1), the Firebase verification TXT,
# two DKIM CNAMEs and a DMARC record. All DNS-only. Names are relative to the zone.

locals {
  # "@" for the apex, otherwise the sending domain without the zone suffix.
  label  = var.domain == var.zone_name ? "@" : trimsuffix(var.domain, ".${var.zone_name}")
  suffix = local.label == "@" ? "" : ".${local.label}"

  spf = join(" ", concat(["v=spf1"], [for h in var.spf_includes : "include:${h}"], ["~all"]))

  dashed = replace(var.domain, ".", "-")
  dkim_targets = var.dkim_targets != null ? var.dkim_targets : {
    firebase1 = "mail-${local.dashed}.dkim1._domainkey.firebasemail.com"
    firebase2 = "mail-${local.dashed}.dkim2._domainkey.firebasemail.com"
  }

  dmarc = "v=DMARC1; p=${var.dmarc_policy}${var.dmarc_report_address != "" ? "; rua=mailto:${var.dmarc_report_address}" : ""}"
}

resource "cloudflare_record" "spf" {
  count   = var.enabled ? 1 : 0
  zone_id = var.zone_id
  name    = local.label
  type    = "TXT"
  content = local.spf
  proxied = false
  ttl     = 300
  comment = "Sign-in email SPF (Terraform)"
}

resource "cloudflare_record" "verification" {
  count   = var.enabled ? 1 : 0
  zone_id = var.zone_id
  name    = local.label
  type    = "TXT"
  content = "firebase=${var.project_id}"
  proxied = false
  ttl     = 300
  comment = "Sign-in email domain verification (Terraform)"
}

resource "cloudflare_record" "dkim" {
  for_each = var.enabled ? local.dkim_targets : {}
  zone_id  = var.zone_id
  name     = "${each.key}._domainkey${local.suffix}"
  type     = "CNAME"
  content  = each.value
  proxied  = false
  ttl      = 300
  comment  = "Sign-in email DKIM (Terraform)"
}

resource "cloudflare_record" "dmarc" {
  count   = var.enabled ? 1 : 0
  zone_id = var.zone_id
  name    = "_dmarc${local.suffix}"
  type    = "TXT"
  content = local.dmarc
  proxied = false
  ttl     = 300
  comment = "Sign-in email DMARC (Terraform)"
}
