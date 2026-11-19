// Refuses cross-site posts. A browser always sends Origin on a cross-site POST; Sec-Fetch-Site covers
// same-origin requests that omit it.
export function isSameOrigin(request: Request, siteOrigin: string): boolean {
  const expected = siteOrigin.replace(/\/+$/, ""); // the setting may end with a slash; an Origin never does
  if (expected === "") return false; // a missing setting refuses every request
  const origin = request.headers.get("origin");
  if (origin !== null) return origin === expected;
  return request.headers.get("sec-fetch-site") === "same-origin";
}
