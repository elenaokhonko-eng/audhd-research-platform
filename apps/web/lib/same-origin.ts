// Refuses cross-site posts. A browser always sends Origin on a cross-site POST; Sec-Fetch-Site covers
// same-origin requests that omit it.
export function isSameOrigin(request: Request, siteOrigin: string): boolean {
  const origin = request.headers.get("origin");
  if (origin !== null) return origin === siteOrigin;
  return request.headers.get("sec-fetch-site") === "same-origin";
}
