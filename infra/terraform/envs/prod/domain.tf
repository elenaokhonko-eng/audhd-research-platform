# Custom domains on Cloudflare DNS (ADR 0003). Records are DNS-only (grey cloud):
# Google must see its own IPs to issue the certificate.
#
#   audhdneurobiology.org      -> web-prod   (A + AAAA)
#   www.audhdneurobiology.org  -> web-prod   (CNAME ghs.googlehosted.com)
#
# dev.audhdneurobiology.org is mapped from the dev project (envs/dev/main.tf).

locals {
  mappings = var.map_custom_domains ? {
    apex = { host = var.domain, service = module.web_prod.name }
    www  = { host = "www.${var.domain}", service = module.web_prod.name }
  } : {}

  # Fixed anycast addresses Cloud Run domain mappings hand out for apex domains.
  # The mapping's own status lists them too: terraform output domain_records.
  apex_a    = ["216.239.32.21", "216.239.34.21", "216.239.36.21", "216.239.38.21"]
  apex_aaaa = ["2001:4860:4802:32::15", "2001:4860:4802:34::15", "2001:4860:4802:36::15", "2001:4860:4802:38::15"]
  dns_on    = var.manage_cloudflare_dns && var.map_custom_domains
}

resource "google_cloud_run_domain_mapping" "this" {
  for_each = local.mappings
  location = var.region
  name     = each.value.host

  metadata {
    namespace = data.google_project.this.project_id
  }

  spec {
    route_name = each.value.service
  }
}

resource "cloudflare_record" "apex_a" {
  for_each = local.dns_on ? toset(local.apex_a) : toset([])
  zone_id  = var.cloudflare_zone_id
  name     = "@"
  type     = "A"
  content  = each.value
  proxied  = false
  ttl      = 300
  comment  = "Cloud Run domain mapping (Terraform)"
}

resource "cloudflare_record" "apex_aaaa" {
  for_each = local.dns_on ? toset(local.apex_aaaa) : toset([])
  zone_id  = var.cloudflare_zone_id
  name     = "@"
  type     = "AAAA"
  content  = each.value
  proxied  = false
  ttl      = 300
  comment  = "Cloud Run domain mapping (Terraform)"
}

resource "cloudflare_record" "cname" {
  for_each = local.dns_on ? toset(["www"]) : toset([])
  zone_id  = var.cloudflare_zone_id
  name     = each.value
  type     = "CNAME"
  content  = "ghs.googlehosted.com"
  proxied  = false
  ttl      = 300
  comment  = "Cloud Run domain mapping (Terraform)"
}
