# Firestore's schema of the platform: the composite indexes its queries need and the
# time-to-live policies of the records with a stated lifetime.
#
# Single-field look-ups need no resource here: Firestore indexes every single field by itself.
# That covers entitlements by contact_id, by member_uid and by source, and contacts by
# channels.platform.member_uid. Do not add indexes for them.

locals {
  # Composite indexes, one per query that filters or orders on more than one field.
  indexes = {
    sync_runs_by_kind = {
      collection = "sync_runs"
      fields = [
        { path = "kind", order = "ASCENDING" },
        { path = "finished_at", order = "DESCENDING" },
      ]
    }
    sync_runs_by_kind_state_dry_run = {
      collection = "sync_runs"
      fields = [
        { path = "kind", order = "ASCENDING" },
        { path = "state", order = "ASCENDING" },
        { path = "dry_run", order = "ASCENDING" },
        { path = "finished_at", order = "DESCENDING" },
      ]
    }
    # Commerce's roster import reads the latest real reconcile: kind == ..., dry_run == false,
    # newest finished_at first.
    sync_runs_by_kind_dry_run = {
      collection = "sync_runs"
      fields = [
        { path = "kind", order = "ASCENDING" },
        { path = "dry_run", order = "ASCENDING" },
        { path = "finished_at", order = "DESCENDING" },
      ]
    }
    downloads_by_member = {
      collection = "downloads"
      fields = [
        { path = "member_uid", order = "ASCENDING" },
        { path = "at", order = "ASCENDING" },
      ]
    }
    entitlements_by_status = {
      collection = "entitlements"
      fields = [
        { path = "status", order = "ASCENDING" },
        { path = "valid_until", order = "ASCENDING" },
      ]
    }
    audit_log_by_subject = {
      collection = "audit_log"
      fields = [
        { path = "subject", order = "ASCENDING" },
        { path = "at", order = "ASCENDING" },
      ]
    }
  }

  # Collections whose records carry expires_at, written by the code when it creates the record
  # from the lifetimes in the privacy notice: downloads and support requests 12 months, audit
  # records 24 months, rate-limit counters 2 days.
  expiring_collections = toset(["downloads", "support_requests", "audit_log", "rate_limits"])
}

resource "google_firestore_index" "this" {
  for_each    = local.indexes
  project     = var.project_id
  database    = var.database
  collection  = each.value.collection
  query_scope = "COLLECTION"

  dynamic "fields" {
    for_each = each.value.fields
    content {
      field_path = fields.value.path
      order      = fields.value.order
    }
  }
}

# Firestore deletes a record once its expires_at has passed. Deletion is not immediate: Google
# removes an expired document within about a day, which the privacy notice's periods allow for.
resource "google_firestore_field" "expires" {
  for_each   = local.expiring_collections
  project    = var.project_id
  database   = var.database
  collection = each.value
  field      = "expires_at"

  ttl_config {}

  # Only the policy reads this timestamp, so it is exempt from single-field indexing, as
  # Google recommends.
  index_config {}
}
