// In-memory stand-in for platform-api, built on the shared test people. Never used in prod.
import { people } from "../../tests/fixtures/people";
import { ApiError } from "./errors";
import type { PlatformApi } from "./client";
import type {
  Access,
  ApiErrorCode,
  Campaign,
  ItemCard,
  ItemDetail,
  Member,
  Promotion,
  Reason,
  RefreshTicket,
  SessionResult,
  SignedLink,
  UpgradeOptions,
} from "./types";

const TERMS_VERSION = "terms-v1";
const PRIVACY_VERSION = "privacy-v1";
const NOW = "2026-11-20T00:00:00Z";
const SESSION_EXPIRES = "2027-01-20T00:00:00Z";

const DEFAULT_CAMPAIGN: Campaign = {
  slug: null,
  audience: "guests",
  state: "open",
  copy: { headline: "Join the newsletter", body: "Create your free workspace.", cta: "Join" },
};

const card = (sku: string, title: string, kind: ItemCard["kind"], access: ItemCard["access"], buy_url: string | null) => ({
  sku,
  title,
  kind,
  abstract: `An invented abstract for ${title.toLowerCase()}.`,
  version: "1.0",
  pages: 12,
  access,
  buy_url,
});

const ITEMS = [
  card("sample-map", "Sample map", "evidence_map", "paid", "https://example.org/buy/sample-map"),
  card("sample-guide", "Sample guide", "guide", "free_members", null),
  card("sample-book", "Sample book", "guide", "purchase_only", null),
];

export class FakePlatformApi implements PlatformApi {
  private readonly accepted = new Set<string>();
  private readonly sessions = new Set<string>();
  private readonly joinedVia = new Map<string, string | null>();
  private failure: ApiErrorCode | null = null;
  private promotion: Promotion | null = null;
  private readonly upgradeOnRefresh = new Set<string>();
  private readonly upgraded = new Set<string>();
  private readonly refreshed = new Set<string>();

  setPromotion(promotion: Promotion | null): void {
    this.promotion = promotion;
  }

  upgradeAfterRefresh(name: string): void {
    this.upgradeOnRefresh.add(name);
  }

  // A member route other than the four of contracts section 1: needs a session and accepted terms.
  private gated(session: string): string {
    const name = this.nameFrom(session);
    if (!this.accepted.has(name)) throw new ApiError(409, "terms_required", "Accept the terms first.", null);
    return name;
  }

  private tier(name: string): "free" | "paid" {
    return this.upgraded.has(name) ? "paid" : people.find((x) => x.name === name)!.tier;
  }

  private cardFor(name: string, item: (typeof ITEMS)[number]): ItemCard {
    const can_open = item.access === "free_members" || (item.access === "paid" && this.tier(name) === "paid");
    return { ...item, can_open };
  }

  failNext(code: ApiErrorCode): void {
    this.failure = code;
  }

  private maybeFail(): void {
    if (this.failure) {
      const code = this.failure;
      this.failure = null;
      const status = { unauthenticated: 401, forbidden: 403, not_found: 404, terms_required: 409, validation_failed: 422, rate_limited: 429, unavailable: 503 }[code];
      throw new ApiError(status, code, `Fake failure: ${code}`, code === "rate_limited" ? 30 : null);
    }
  }

  private nameFrom(session: string): string {
    const name = session.startsWith("fake-session:") ? session.slice("fake-session:".length) : "";
    if (!this.sessions.has(name)) throw new ApiError(401, "unauthenticated", "No valid session.", null);
    return name;
  }

  private member(name: string): Member {
    const p = people.find((x) => x.name === name)!;
    return {
      uid: `uid-${name}`,
      display_name: null,
      email_hint: `${p.email[0]}…@example.org`,
      terms: {
        accepted: this.accepted.has(name),
        terms_version: this.accepted.has(name) ? TERMS_VERSION : null,
        privacy_version: this.accepted.has(name) ? PRIVACY_VERSION : null,
        required: { terms_version: TERMS_VERSION, privacy_version: PRIVACY_VERSION },
      },
      joined_via: this.joinedVia.get(name) ?? null,
      status: "active",
    };
  }

  private access(name: string): Access {
    const p = people.find((x) => x.name === name)!;
    return {
      tier: this.tier(name),
      sections:
        this.tier(name) === "paid"
          ? ["overview", "library", "account", "research", "guides"]
          : ["overview", "library", "account"],
      items: [],
      reasons: p.reasons.map((r) => ({ ...r })),
      computed_at: NOW,
    };
  }

  async campaign(slug: string | null): Promise<Campaign> {
    this.maybeFail();
    if (slug === "closed") {
      return {
        slug: "closed",
        audience: "guests",
        state: "closed",
        copy: { headline: "Joining is closed", body: "Joining is not open right now.", cta: "Back" },
      };
    }
    return { ...DEFAULT_CAMPAIGN, copy: { ...DEFAULT_CAMPAIGN.copy } };
  }

  async resolveSession(idToken: string, campaign: string | null): Promise<SessionResult> {
    this.maybeFail();
    const name = idToken.startsWith("fake-token:") ? idToken.slice("fake-token:".length) : "";
    const p = people.find((x) => x.name === name);
    if (!p) throw new ApiError(401, "unauthenticated", "The sign-in token is not valid.", null);
    this.sessions.add(name);
    if (!this.joinedVia.has(name)) this.joinedVia.set(name, campaign);
    const access = this.access(name);
    const grant = p.reasons.find((r) => r.label === "launch_grant");
    return {
      session: { cookie: `fake-session:${name}`, expires_at: SESSION_EXPIRES },
      member: this.member(name),
      access,
      join: {
        campaign,
        recognition: p.tier,
        source_checked_at: NOW,
        check: "fresh",
        grant: name === "ana" && grant ? { created: true, valid_until: grant.valid_until! } : null,
      },
    };
  }

  async revokeSession(session: string): Promise<void> {
    this.maybeFail();
    const name = session.startsWith("fake-session:") ? session.slice("fake-session:".length) : "";
    this.sessions.delete(name);
  }

  async me(session: string): Promise<{ member: Member; access: Access }> {
    this.maybeFail();
    const name = this.nameFrom(session);
    return { member: this.member(name), access: this.access(name) };
  }

  async acceptTerms(session: string, termsVersion: string, privacyVersion: string): Promise<Member> {
    this.maybeFail();
    const name = this.nameFrom(session);
    if (termsVersion !== TERMS_VERSION || privacyVersion !== PRIVACY_VERSION) {
      throw new ApiError(422, "validation_failed", "These are not the current versions.", null);
    }
    this.accepted.add(name);
    return this.member(name);
  }

  async supportRequest(
    session: string,
    _kind: "paid_not_recognised" | "other",
    note: string,
  ): Promise<{ id: string }> {
    this.maybeFail();
    const name = this.nameFrom(session);
    if (!this.accepted.has(name)) throw new ApiError(409, "terms_required", "Accept the terms first.", null);
    if (note.length > 500) throw new ApiError(422, "validation_failed", "The note is too long.", null);
    return { id: `support-${name}-1` };
  }

  async entitlements(session: string): Promise<Reason[]> {
    this.maybeFail();
    const name = this.gated(session);
    return people.find((x) => x.name === name)!.reasons.map((r) => ({ ...r }));
  }

  async refreshAccess(session: string): Promise<RefreshTicket> {
    this.maybeFail();
    const name = this.gated(session);
    const next = "2026-11-20T00:01:00Z";
    if (this.refreshed.has(name)) return { check: "already_running", last_completed_at: null, next_allowed_at: next };
    this.refreshed.add(name);
    if (this.upgradeOnRefresh.has(name)) this.upgraded.add(name);
    return { check: "started", last_completed_at: null, next_allowed_at: next };
  }

  async upgradeOptions(session: string): Promise<UpgradeOptions> {
    this.maybeFail();
    const name = this.gated(session);
    if (this.tier(name) === "paid") return { routes: [], promotion: null };
    const p = people.find((x) => x.name === name)!;
    if (p.reasons.some((r) => r.label === "substack_status")) {
      return {
        routes: [{ kind: "substack_change_plan", available: true, url: "https://example.org/subscribe" }],
        promotion: null,
      };
    }
    return {
      routes: [
        { kind: "substack", available: true, url: this.promotion?.url ?? "https://example.org/subscribe" },
        { kind: "platform_only", available: false, url: null },
      ],
      promotion: this.promotion,
    };
  }

  async activePromotions(): Promise<Promotion[]> {
    this.maybeFail();
    return this.promotion ? [this.promotion] : [];
  }

  async libraryItems(session: string): Promise<ItemCard[]> {
    this.maybeFail();
    const name = this.gated(session);
    return ITEMS.map((i) => this.cardFor(name, i)).sort((a, b) =>
      a.title.toLowerCase().localeCompare(b.title.toLowerCase()),
    );
  }

  async libraryItem(session: string, sku: string): Promise<ItemDetail> {
    this.maybeFail();
    const name = this.gated(session);
    const item = ITEMS.find((i) => i.sku === sku);
    if (!item) throw new ApiError(404, "not_found", "There is no such item.", null);
    return { item: this.cardFor(name, item), description: `An invented description of ${item.title.toLowerCase()}.`, citation: null };
  }

  async download(session: string, sku: string): Promise<SignedLink> {
    this.maybeFail();
    const name = this.gated(session);
    const item = ITEMS.find((i) => i.sku === sku);
    if (!item) throw new ApiError(404, "not_found", "There is no such item.", null);
    if (!this.cardFor(name, item).can_open) {
      const reason = item.access === "paid" ? "paid_required" : "purchase_required";
      throw new ApiError(403, "forbidden", "This item is not included in your access.", null, reason);
    }
    return { url: `https://files.invalid/${sku}`, expires_at: new Date(Date.now() + 10 * 60 * 1000).toISOString() };
  }

  async requestDeletion(session: string): Promise<void> {
    this.maybeFail();
    const name = this.nameFrom(session);
    this.sessions.delete(name);
  }
}
