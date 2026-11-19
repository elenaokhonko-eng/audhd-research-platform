import {
  createFakeAuthClient,
  createFirebaseAuthClient,
  type AuthClient,
} from "./auth-client";
import type { IdentityConfig } from "./config";

export type PostSession = (idToken: string, campaign: string | null) => Promise<{ next: string }>;

export const defaultPostSession: PostSession = async (idToken, campaign) => {
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id_token: idToken, campaign }),
  });
  if (response.status !== 200) throw new Error("session_failed");
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
