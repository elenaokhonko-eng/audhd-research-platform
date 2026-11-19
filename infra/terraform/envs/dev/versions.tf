terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.10"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.40"
    }
  }

  # State lives in a versioned bucket created by ops/scripts/20-stage1-foundations.sh.
  # The bucket name is passed at init time:
  #   terraform init -backend-config="bucket=audhd-neurobiology-dev-tfstate"
  backend "gcs" {
    prefix = "platform"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region

  # With user credentials some APIs need an explicit quota project; use this one.
  user_project_override = true
  billing_project       = var.project_id
}

# Only used when manage_cloudflare_dns = true. Token needs Zone:DNS:Edit on audhdneurobiology.org.
# Pass it as TF_VAR_cloudflare_api_token; never commit it.
provider "cloudflare" {
  api_token = var.manage_cloudflare_dns ? var.cloudflare_api_token : "0000000000000000000000000000000000000000"
}
