import {
  createFakeAuthClient,
  createFirebaseAuthClient,
  type AuthClient,
} from "./auth-client";
import type { IdentityConfig } from "./config";

export type PostSession = (idToken: string, campaign: string | null) => Promise<{ next: string }>;

// A refusal from /api/session. Carries the HTTP status only: never the token or an address.
export class SessionError extends Error {
  constructor(readonly status: number) {
    super("session_failed");
    this.name = "SessionError";
  }
}

// Worth sending the same token again: the service was unavailable (503) or the request never got an answer.
export function isRetryable(error: unknown): boolean {
  return !(error instanceof SessionError) || error.status === 503;
}

export const defaultPostSession: PostSession = async (idToken, campaign) => {
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id_token: idToken, campaign }),
  });
  if (response.status !== 200) throw new SessionError(response.status);
  return (await response.json()) as { next: string };
};

export const defaultNavigate = (url: string): void => window.location.assign(url);

// The client a screen should use: the one passed in, else one built from the configuration.
export function buildAuthClient(identity: IdentityConfig, authClient?: AuthClient): AuthClient | null {
  if (identity.kind === "missing") return null;
  if (authClient) return authClient;
  if (identity.kind === "fake") return createFakeAuthClient();
  if (identity.kind === "firebase") {
    return createFirebaseAuthClient({ apiKey: identity.apiKey, authDomain: identity.authDomain });
  }
  return null;
}
