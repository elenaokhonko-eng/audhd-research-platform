import { GoogleAuth } from "google-auth-library";
import { ApiError } from "./errors";
import { FakePlatformApi } from "./fake";
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

export { ApiError };

export interface PlatformApi {
  campaign(slug: string | null): Promise<Campaign>;
  resolveSession(idToken: string, campaign: string | null): Promise<SessionResult>;
  revokeSession(session: string): Promise<void>;
  me(session: string): Promise<{ member: Member; access: Access }>;
  acceptTerms(session: string, termsVersion: string, privacyVersion: string): Promise<Member>;
  supportRequest(
    session: string,
    kind: "paid_not_recognised" | "other",
    note: string,
  ): Promise<{ id: string }>;
  entitlements(session: string): Promise<Reason[]>;
  refreshAccess(session: string): Promise<RefreshTicket>;
  upgradeOptions(session: string): Promise<UpgradeOptions>;
  activePromotions(): Promise<Promotion[]>;
  libraryItems(session: string): Promise<ItemCard[]>;
  libraryItem(session: string, sku: string): Promise<ItemDetail>;
  download(session: string, sku: string): Promise<SignedLink>;
  requestDeletion(session: string): Promise<void>;
}

const CODES: ApiErrorCode[] = [
  "unauthenticated",
  "forbidden",
  "not_found",
  "terms_required",
  "validation_failed",
  "rate_limited",
  "unavailable",
];

const unavailable = () => new ApiError(503, "unavailable", "The service could not be reached.", null);

export class HttpPlatformApi implements PlatformApi {
  constructor(
    private readonly baseUrl: string,
    private readonly idToken: () => Promise<string>,
    private readonly fetchImpl: typeof fetch = fetch,
    private readonly timeoutMs: number = 10000,
  ) {}

  private async call<T>(
    method: "GET" | "POST",
    path: string,
    opts: { session?: string; body?: unknown } = {},
  ): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let response: Response;
    try {
      const headers = new Headers({ authorization: `Bearer ${await this.idToken()}` });
      if (opts.session !== undefined) headers.set("x-member-session", opts.session);
      const init: RequestInit = { method, headers, signal: controller.signal };
      if (opts.body !== undefined) {
        headers.set("content-type", "application/json");
        init.body = JSON.stringify(opts.body);
      }
      response = await this.fetchImpl(`${this.baseUrl}${path}`, init);
      if (response.ok) return (await response.json()) as T;
    } catch {
      throw unavailable();
    } finally {
      clearTimeout(timer);
    }
    let parsed: { error?: { code?: string; message?: string; retry_after?: number | null; reason?: string | null } };
    try {
      parsed = await response.json();
    } catch {
      throw unavailable();
    }
    const err = parsed?.error;
    if (!err || !CODES.includes(err.code as ApiErrorCode)) throw unavailable();
    throw new ApiError(
      response.status,
      err.code as ApiErrorCode,
      err.message ?? "",
      err.retry_after ?? null,
      err.reason === "paid_required" || err.reason === "purchase_required" ? err.reason : null,
    );
  }

  campaign(slug: string | null): Promise<Campaign> {
    return this.call("GET", `/v1/public/campaigns/${encodeURIComponent(slug ?? "default")}`);
  }

  resolveSession(idToken: string, campaign: string | null): Promise<SessionResult> {
    return this.call("POST", "/v1/session/resolve", { body: { id_token: idToken, campaign } });
  }

  async revokeSession(session: string): Promise<void> {
    await this.call("POST", "/v1/session/revoke", { session });
  }

  me(session: string): Promise<{ member: Member; access: Access }> {
    return this.call("GET", "/v1/me", { session });
  }

  async acceptTerms(session: string, termsVersion: string, privacyVersion: string): Promise<Member> {
    const out = await this.call<{ member: Member }>("POST", "/v1/me/terms-acceptance", {
      session,
      body: { terms_version: termsVersion, privacy_version: privacyVersion },
    });
    return out.member;
  }

  supportRequest(
    session: string,
    kind: "paid_not_recognised" | "other",
    note: string,
  ): Promise<{ id: string }> {
    return this.call("POST", "/v1/me/support-requests", { session, body: { kind, note } });
  }

  async entitlements(session: string): Promise<Reason[]> {
    return (await this.call<{ entitlements: Reason[] }>("GET", "/v1/me/entitlements", { session })).entitlements;
  }

  refreshAccess(session: string): Promise<RefreshTicket> {
    return this.call("POST", "/v1/me/refresh-access", { session });
  }

  upgradeOptions(session: string): Promise<UpgradeOptions> {
    return this.call("GET", "/v1/me/upgrade-options", { session });
  }

  async activePromotions(): Promise<Promotion[]> {
    return (await this.call<{ promotions: Promotion[] }>("GET", "/v1/public/promotions/active")).promotions;
  }

  async libraryItems(session: string): Promise<ItemCard[]> {
    return (await this.call<{ items: ItemCard[] }>("GET", "/v1/library/items", { session })).items;
  }

  libraryItem(session: string, sku: string): Promise<ItemDetail> {
    return this.call("GET", `/v1/library/items/${encodeURIComponent(sku)}`, { session });
  }

  download(session: string, sku: string): Promise<SignedLink> {
    return this.call("POST", `/v1/library/items/${encodeURIComponent(sku)}/download`, { session });
  }

  async requestDeletion(session: string): Promise<void> {
    await this.call("POST", "/v1/me/deletion-request", { session });
  }
}

// One fake per server process (kept on globalThis so Next dev reloads keep it), so sessions and
// accepted terms survive from one request to the next.
const globalForFake = globalThis as typeof globalThis & { __platformApiFake?: FakePlatformApi };

// One id-token client per audience, built lazily and reused.
const tokenProviders = new Map<string, () => Promise<string>>();

function idTokenFor(audience: string): () => Promise<string> {
  let provider = tokenProviders.get(audience);
  if (!provider) {
    let client: ReturnType<GoogleAuth["getIdTokenClient"]> | undefined;
    provider = async () => {
      client ??= new GoogleAuth().getIdTokenClient(audience);
      try {
        return await (await client).idTokenProvider.fetchIdToken(audience);
      } catch (error) {
        client = undefined;
        throw error;
      }
    };
    tokenProviders.set(audience, provider);
  }
  return provider;
}

export function getPlatformApi(env: Record<string, string | undefined> = process.env): PlatformApi {
  if (env.PLATFORM_API_FAKE === "1") {
    if (env.SITE_ENV === "prod") throw new Error("PLATFORM_API_FAKE is not allowed in prod");
    return (globalForFake.__platformApiFake ??= new FakePlatformApi());
  }
  const url = env.PLATFORM_API_URL;
  if (!url) throw new Error("PLATFORM_API_URL is not set");
  return new HttpPlatformApi(url, idTokenFor(url));
}
