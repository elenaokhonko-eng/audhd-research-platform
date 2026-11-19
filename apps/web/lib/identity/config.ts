export type IdentityConfig =
  | { kind: "firebase"; apiKey: string; authDomain: string }
  | { kind: "fake" }
  | { kind: "missing" };

export function identityConfig(env: Record<string, string | undefined> = process.env): IdentityConfig {
  if (env.PLATFORM_API_FAKE === "1" && env.SITE_ENV !== "prod") return { kind: "fake" };
  const apiKey = env.IDENTITY_API_KEY;
  const authDomain = env.IDENTITY_AUTH_DOMAIN;
  if (apiKey && authDomain) return { kind: "firebase", apiKey, authDomain };
  return { kind: "missing" };
}
