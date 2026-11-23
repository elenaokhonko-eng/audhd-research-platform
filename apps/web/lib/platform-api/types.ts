// Shapes of docs/contracts/stage-1-launch.md section 2. Change only through a contract-change pull request.

export type ApiErrorCode =
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "terms_required"
  | "validation_failed"
  | "rate_limited"
  | "unavailable";

export interface Member {
  uid: string;
  display_name: string | null;
  email_hint: string;
  terms: {
    accepted: boolean;
    terms_version: string | null;
    privacy_version: string | null;
    required: { terms_version: string; privacy_version: string };
  };
  joined_via: string | null;
  status: string;
}

export interface Reason {
  grant: string;
  source: "substack_stripe" | "substack_roster" | "platform_stripe" | "payhip" | "grant";
  label:
    | "substack_subscription"
    | "substack_status"
    | "launch_grant"
    | "owner_grant"
    | "purchase"
    | "platform_subscription";
  access_scope: string;
  status: string;
  valid_until: string | null;
  campaign: string | null;
  plan_interval: "month" | "year" | null;
}

export interface Access {
  tier: "free" | "paid";
  sections: string[];
  items: string[];
  reasons: Reason[];
  computed_at: string;
}

export interface Join {
  campaign: string | null;
  recognition: "paid" | "free";
  source_checked_at: string;
  check: "fresh" | "started";
  grant: { created: boolean; valid_until: string } | null;
}

export interface Campaign {
  slug: string | null;
  audience: string;
  state: "scheduled" | "open" | "closed";
  copy: { headline: string; body: string; cta: string };
}

export interface SessionResult {
  session: { cookie: string; expires_at: string };
  member: Member;
  access: Access;
  join: Join;
}

export interface Route {
  kind: "substack" | "platform_only" | "substack_change_plan";
  available: boolean;
  url: string | null;
}

export interface Promotion {
  id: string;
  channel: string;
  plan_interval: "month" | "year" | null;
  starts_at: string;
  ends_at: string;
  url: string | null;
  display: { badge: string; headline: string; body: string };
}

export interface UpgradeOptions {
  routes: Route[];
  promotion: Promotion | null;
}

export interface RefreshTicket {
  check: "fresh" | "started" | "already_running";
  last_completed_at: string | null;
  next_allowed_at: string;
}

export type ItemKind = "meta_review" | "evidence_map" | "clinician_one_pager" | "guide" | "worksheet";

export interface ItemCard {
  sku: string;
  title: string;
  kind: ItemKind;
  abstract: string;
  version: string;
  pages: number;
  access: "paid" | "free_members" | "purchase_only";
  can_open: boolean;
  buy_url: string | null;
}

export interface ItemDetail {
  item: ItemCard;
  description: string;
  citation: string | null;
}

export interface SignedLink {
  url: string;
  expires_at: string;
}

export type ErrorReason = "paid_required" | "purchase_required";
