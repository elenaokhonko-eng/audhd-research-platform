export const SESSION_COOKIE = "session";

function attributes(siteEnv: string): string[] {
  const parts = ["Path=/", "HttpOnly", "SameSite=Lax"];
  if (siteEnv !== "local") parts.push("Secure");
  return parts;
}

export function sessionCookieHeader(value: string, expiresAt: string, siteEnv: string): string {
  const parts = [`${SESSION_COOKIE}=${value}`, ...attributes(siteEnv)];
  const when = new Date(expiresAt);
  if (!Number.isNaN(when.getTime())) parts.push(`Expires=${when.toUTCString()}`);
  return parts.join("; ");
}

export function clearSessionCookieHeader(siteEnv: string): string {
  return [`${SESSION_COOKIE}=`, ...attributes(siteEnv), "Max-Age=0", "Expires=Thu, 01 Jan 1970 00:00:00 GMT"].join("; ");
}

export function readSessionCookie(cookieHeader: string | null): string | null {
  if (!cookieHeader) return null;
  for (const part of cookieHeader.split(";")) {
    const index = part.indexOf("=");
    if (index === -1) continue;
    if (part.slice(0, index).trim() === SESSION_COOKIE) {
      const value = part.slice(index + 1).trim();
      return value === "" ? null : value;
    }
  }
  return null;
}
