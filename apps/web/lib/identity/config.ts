export type IdentityConfig =
  | { kind: "firebase"; apiKey: string; authDomain: string; googleEnabled: boolean }
  | { kind: "fake"; googleEnabled: boolean }
  | { kind: "missing" };

export function identityConfig(env: Record<string, string | undefined> = process.env): IdentityConfig {
  if (env.PLATFORM_API_FAKE === "1" && env.SITE_ENV !== "prod") return { kind: "fake", googleEnabled: true };
  const apiKey = env.IDENTITY_API_KEY;
  const authDomain = env.IDENTITY_AUTH_DOMAIN;
  if (apiKey && authDomain) return { kind: "firebase", apiKey, authDomain, googleEnabled: env.IDENTITY_GOOGLE_ENABLED === "1" };
  return { kind: "missing" };
}
