import { GoogleAuth } from "google-auth-library";
import { ApiError } from "./errors";
import { FakePlatformApi } from "./fake";
import type { Access, ApiErrorCode, Campaign, Member, SessionResult } from "./types";

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
    let parsed: { error?: { code?: string; message?: string; retry_after?: number | null } };
    try {
      parsed = await response.json();
    } catch {
      throw unavailable();
    }
    const err = parsed?.error;
    if (!err || !CODES.includes(err.code as ApiErrorCode)) throw unavailable();
    throw new ApiError(response.status, err.code as ApiErrorCode, err.message ?? "", err.retry_after ?? null);
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
}

export function getPlatformApi(env: Record<string, string | undefined> = process.env): PlatformApi {
  if (env.PLATFORM_API_FAKE === "1") {
    if (env.SITE_ENV === "prod") throw new Error("PLATFORM_API_FAKE is not allowed in prod");
    return new FakePlatformApi();
  }
  const url = env.PLATFORM_API_URL;
  if (!url) throw new Error("PLATFORM_API_URL is not set");
  const auth = new GoogleAuth();
  return new HttpPlatformApi(url, async () => {
    const client = await auth.getIdTokenClient(url);
    return client.idTokenProvider.fetchIdToken(url);
  });
}
