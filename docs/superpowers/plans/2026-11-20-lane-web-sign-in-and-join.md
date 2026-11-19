# Lane L2 Web · Sign-in, Join and Welcome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reader opens `/join` or `/join/<slug>`, signs in by emailed link or with Google, accepts the terms, and lands on a welcome page that says in plain words whether they were recognised as a paid subscriber.

**Architecture:** The browser talks only to this Next.js app. Server code calls `platform-api` through one typed client (`PlatformApi`); a fake with the shared invented people stands in for it in tests and on a developer's machine, so this lane does not wait for the backend. Sign-in with Identity Platform is wrapped in one small interface (`AuthClient`), so pages are tested without a network. The member's session is an http-only cookie set by a route handler.

**Tech Stack:** Next.js 16 (app router, `output: "standalone"`), React 19, TypeScript strict; new runtime dependencies `firebase` (modular `firebase/auth`) and `google-auth-library`; new dev dependencies `vitest`, `@vitejs/plugin-react`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`.

**Spec:** [launch design](../specs/2026-11-19-launch-invites-grants-promotions-design.md) §5.2, §5.6 · [contracts](../../contracts/stage-1-launch.md) §1, §2, §8 · task cards W1 and W2 of the [swarm build plan](../../plans/stage-1-swarm-build-plan.md).

**Lane rules:** change only `apps/web/`. Branch from `integration/stage-1`; one pull request per task. The one change outside the lane (a test step in CI) is a separate pull request labelled `cross-lane`.

## Global Constraints

- The browser never calls `platform-api`. Client components call this app's own `/api/*` routes.
- Server code reaches `platform-api` only through `getPlatformApi()`. Requests carry a Google identity token for the audience `PLATFORM_API_URL` and, when a member is signed in, the header `X-Member-Session`.
- Shapes and names come from the contracts page. If a shape is missing there, stop and ask the integrator; do not invent one.
- No email address in a URL, a log line, an error message sent to the browser, or an analytics call. The only place the address is kept is `localStorage["signin.email"]`, from sending the link until the sign-in completes.
- Session cookie: name `session`; `HttpOnly`; `SameSite=Lax`; `Path=/`; `Secure` unless `SITE_ENV` is `local`; expiry taken from `session.expires_at`.
- Every state-changing route under `/api/` refuses a request that is not same-origin (Task 2).
- Runtime configuration is read on the server at request time and passed to client components as props. Do not use `NEXT_PUBLIC_` variables: the same image runs in dev and prod.
- Environment variables this lane reads: `SITE_ENV` (`local`, `dev`, `prod`), `SITE_ORIGIN`, `PLATFORM_API_URL`, `PLATFORM_API_FAKE`, `IDENTITY_API_KEY`, `IDENTITY_AUTH_DOMAIN`, `SIGNIN_SENDER_HINT` (optional).
- Test people are the shared invented ones at `example.org` ([contracts §8](../../contracts/stage-1-launch.md)). Tests never call Identity Platform or `platform-api`.
- Wording is literal and plain: no idioms, one instruction per sentence. Every control has a visible label. Status changes are announced in an `aria-live="polite"` region. Everything works by keyboard.
- A slug is valid only if it matches `^[a-z0-9-]{1,40}$`. Anything else is treated as no slug.

## Review Focus

1. **The link is opened on another device.** No stored email: the page asks for the address the link was sent to, then completes. Pinned in Task 5.
2. **The link is expired or was already used.** A plain message and a way to get a new link; no technical text. Pinned in Task 5.
3. **A request to `/api/session` or `/api/terms` from another site**, or with neither an `Origin` header nor fetch metadata: 403 and no cookie. Pinned in Task 2.
4. **`platform-api` cannot be reached during sign-in.** No cookie is set, the person is told to try again, and trying again works without a new email. Pinned in Tasks 2 and 5.
5. **A slug that is not a slug** (`../admin`, 200 characters, markup): treated as no slug, default wording, never placed into a URL or the page. Pinned in Tasks 2 and 4.

---

## File Structure

```
apps/web/
├─ vitest.config.ts  vitest.setup.ts
├─ lib/platform-api/types.ts      shapes from the contracts page
├─ lib/platform-api/errors.ts     ApiError (its own file: client.ts and fake.ts both import it, and must not import each other in a cycle)
├─ lib/platform-api/client.ts     PlatformApi, HttpPlatformApi, getPlatformApi; re-exports ApiError
├─ lib/platform-api/fake.ts       FakePlatformApi
├─ lib/slug.ts                    cleanSlug
├─ lib/session.ts                 cookie helpers
├─ lib/same-origin.ts             isSameOrigin
├─ lib/identity/auth-client.ts    AuthClient, AuthError, createFirebaseAuthClient, createFakeAuthClient
├─ lib/identity/config.ts         identityConfig
├─ lib/welcome.ts                 welcomeView
├─ app/join/page.tsx  app/join/[slug]/page.tsx  app/join/JoinScreen.tsx
├─ app/auth/finish/page.tsx  app/auth/finish/FinishSignIn.tsx
├─ app/api/session/route.ts  app/api/terms/route.ts  app/api/support/route.ts
├─ app/welcome/page.tsx  app/welcome/TermsStep.tsx  app/welcome/NotRecognised.tsx
├─ app/terms/page.tsx  app/privacy/page.tsx        placeholders until the owner's texts arrive (W6)
└─ tests/fixtures/people.ts  tests/*.test.ts(x)
```

`app/chatgpt-auth.ts` is deleted in Task 1: nothing imports it, and it trusts identity headers from an earlier hosting arrangement.

---

### Task 1: Test tooling, contract types, the API client and its fake

**Files:**
- Create: `apps/web/vitest.config.ts`, `vitest.setup.ts`, `lib/platform-api/types.ts`, `lib/platform-api/errors.ts`, `lib/platform-api/client.ts`, `lib/platform-api/fake.ts`, `tests/fixtures/people.ts`, `tests/platform-api.test.ts`
- Modify: `apps/web/package.json` (scripts `"test": "vitest run"`, `"typecheck": "tsc --noEmit"`; dependencies above)
- Delete: `apps/web/app/chatgpt-auth.ts`

**Interfaces:**
- Produces, in `types.ts`, exactly the shapes of [contracts §2](../../contracts/stage-1-launch.md): `Member`, `Access`, `Reason`, `Join`, `Campaign`, `SessionResult` (`{ session: { cookie: string; expires_at: string }; member: Member; access: Access; join: Join }`), `ApiErrorCode` (`"unauthenticated" | "forbidden" | "not_found" | "terms_required" | "validation_failed" | "rate_limited" | "unavailable"`).
- Produces, in `client.ts`:

```ts
export class ApiError extends Error {
  constructor(readonly status: number, readonly code: ApiErrorCode, message: string, readonly retryAfter: number | null);
}
export interface PlatformApi {
  campaign(slug: string | null): Promise<Campaign>;
  resolveSession(idToken: string, campaign: string | null): Promise<SessionResult>;
  revokeSession(session: string): Promise<void>;
  me(session: string): Promise<{ member: Member; access: Access }>;
  acceptTerms(session: string, termsVersion: string, privacyVersion: string): Promise<Member>;
  supportRequest(session: string, kind: "paid_not_recognised" | "other", note: string): Promise<{ id: string }>;
}
export class HttpPlatformApi implements PlatformApi {
  constructor(baseUrl: string, idToken: () => Promise<string>, fetchImpl?: typeof fetch, timeoutMs?: number);  // timeout default 10000
}
export function getPlatformApi(env?: Record<string, string | undefined>): PlatformApi;
```

- `getPlatformApi`: returns a `FakePlatformApi` when `PLATFORM_API_FAKE` is `"1"`, and throws `Error("PLATFORM_API_FAKE is not allowed in prod")` when `SITE_ENV` is `prod`; otherwise an `HttpPlatformApi` for `PLATFORM_API_URL` whose identity token comes from `google-auth-library` (`new GoogleAuth().getIdTokenClient(audience)`); throws `Error("PLATFORM_API_URL is not set")` when it is missing.
- `FakePlatformApi`: an id token is `fake-token:<name>` and a session is `fake-session:<name>`, where `<name>` is one of the fixture people. A session exists once `resolveSession` has been called for that person; `me`, `acceptTerms` and `supportRequest` with any other session reject as `unauthenticated`. Accepting the terms is remembered for the life of the instance. Like the real service, `supportRequest` rejects with `terms_required` (409) until that person has accepted the terms. `failNext(code: ApiErrorCode)` makes the next call reject with that error. `campaign("closed")` returns a closed campaign; an unknown slug returns the default campaign with `slug: null`.
- `tests/fixtures/people.ts` exports `people`: one entry per fixture person with `name`, `email` (`<name>@example.org`), `tier`, `reasons`, and `termsAccepted` (false for all at first sign-in).

| Person | In the fake |
| --- | --- |
| `ana` | `tier: "paid"`; reasons `substack_subscription` (active) and `launch_grant` (active, `valid_until` set) |
| `bo` | `tier: "free"`; no reasons |
| `ed` | `tier: "free"`; no reasons (he pays with another address) |
| `fay` | `tier: "paid"`; reason `launch_grant` only |
| `hal` | `tier: "paid"`; reason `substack_subscription` only |

- [ ] **Step 1: Write the failing tests**

```ts
// apps/web/tests/platform-api.test.ts
import { describe, expect, it, vi } from "vitest";
import { ApiError, HttpPlatformApi, getPlatformApi } from "@/lib/platform-api/client";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("HttpPlatformApi", () => {
  it("sends the service token and the member session", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json(200, { member: {}, access: {} }));
    const api = new HttpPlatformApi("https://api.internal", async () => "svc-token", fetchImpl);
    await api.me("sess-1");
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("https://api.internal/v1/me");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer svc-token");
    expect(new Headers(init.headers).get("x-member-session")).toBe("sess-1");
  });

  it("posts the token and the campaign to session resolve, without a member session", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json(200, { session: {}, member: {}, access: {}, join: {} }));
    const api = new HttpPlatformApi("https://api.internal", async () => "svc-token", fetchImpl);
    await api.resolveSession("id-token", "founding");
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("https://api.internal/v1/session/resolve");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ id_token: "id-token", campaign: "founding" });
    expect(new Headers(init.headers).has("x-member-session")).toBe(false);
  });

  it("turns the error body into an ApiError", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      json(429, { error: { code: "rate_limited", message: "Too many requests", retry_after: 30 } }),
    );
    const api = new HttpPlatformApi("https://api.internal", async () => "t", fetchImpl);
    await expect(api.me("s")).rejects.toMatchObject({ status: 429, code: "rate_limited", retryAfter: 30 });
  });

  it("reports unavailable when the call fails or times out", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("network down"));
    const api = new HttpPlatformApi("https://api.internal", async () => "t", fetchImpl);
    await expect(api.me("s")).rejects.toMatchObject({ status: 503, code: "unavailable" });
  });

  it("asks the default campaign when there is no slug", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(json(200, { slug: null, state: "open", copy: {} }));
    const api = new HttpPlatformApi("https://api.internal", async () => "t", fetchImpl);
    await api.campaign(null);
    expect(fetchImpl.mock.calls[0][0]).toBe("https://api.internal/v1/public/campaigns/default");
  });
});

describe("getPlatformApi", () => {
  it("refuses the fake in prod", () => {
    expect(() => getPlatformApi({ PLATFORM_API_FAKE: "1", SITE_ENV: "prod" })).toThrow(/not allowed in prod/);
  });
  it("gives the fake elsewhere", () => {
    expect(getPlatformApi({ PLATFORM_API_FAKE: "1", SITE_ENV: "dev" })).toBeInstanceOf(FakePlatformApi);
  });
  it("needs a URL for the real client", () => {
    expect(() => getPlatformApi({ SITE_ENV: "dev" })).toThrow(/PLATFORM_API_URL is not set/);
  });
});

describe("FakePlatformApi", () => {
  it("recognises ana as paid with a launch grant", async () => {
    const result = await new FakePlatformApi().resolveSession("fake-token:ana", "founding");
    expect(result.session.cookie).toBe("fake-session:ana");
    expect(result.join).toMatchObject({ campaign: "founding", recognition: "paid" });
    expect(result.join.grant?.created).toBe(true);
    expect(result.access.reasons.map((r) => r.label).sort()).toEqual(["launch_grant", "substack_subscription"]);
  });
  it("gives bo the free workspace", async () => {
    const result = await new FakePlatformApi().resolveSession("fake-token:bo", null);
    expect(result.join.recognition).toBe("free");
    expect(result.access.tier).toBe("free");
  });
  it("rejects an unknown token as unauthenticated", async () => {
    await expect(new FakePlatformApi().resolveSession("nonsense", null)).rejects.toBeInstanceOf(ApiError);
  });
  it("fails the next call on request", async () => {
    const fake = new FakePlatformApi();
    fake.failNext("unavailable");
    await expect(fake.me("fake-session:bo")).rejects.toMatchObject({ code: "unavailable" });
    await expect(fake.me("fake-session:bo")).resolves.toBeTruthy();
  });
  it("returns the default campaign for an unknown slug and a closed one on request", async () => {
    const fake = new FakePlatformApi();
    expect((await fake.campaign("no-such")).slug).toBeNull();
    expect((await fake.campaign("closed")).state).toBe("closed");
  });
});
```

- [ ] **Step 2: See them fail**

Add the dependencies and the two scripts, write `vitest.config.ts` (environment `jsdom`, alias `@` to the `apps/web` folder, setup file importing `@testing-library/jest-dom/vitest`).
Run: `cd apps/web && npm install && npm test`
Expected: FAIL, cannot resolve `@/lib/platform-api/client`.

- [ ] **Step 3: Write `types.ts`, `client.ts`, `fake.ts`, `people.ts`; delete `app/chatgpt-auth.ts`**

`campaign(null)` asks for the path segment `default`. The contracts page says an unknown slug returns the default campaign, so `default` needs no special route. `HttpPlatformApi` sends `content-type: application/json` on bodies, aborts after `timeoutMs` with `AbortController`, and maps any thrown fetch error, abort, or non-JSON error body to `ApiError(503, "unavailable", ...)`.

- [ ] **Step 4: See them pass**

Run: `npm test && npm run typecheck && npm run build`
Expected: 13 tests passed; no type errors; the build succeeds.

- [ ] **Step 5: Commit, and open the cross-lane pull request**

```bash
git add apps/web
git commit -m "web: test tooling, contract types, platform-api client and its fake"
```

Separately, on a branch `web/ci-run-tests`, add `- run: npm test` after `- run: npm ci` in the `build-test` job of `.github/workflows/web.yml`, and open a pull request labelled `cross-lane` for the Infra lane to review.

---

### Task 2: Session cookie, same-origin check and the session route

**Files:**
- Create: `apps/web/lib/slug.ts`, `lib/session.ts`, `lib/same-origin.ts`, `app/api/session/route.ts`, `tests/session-route.test.ts`

**Interfaces:**
- Consumes: `getPlatformApi`, `ApiError`.
- Produces:

```ts
// lib/slug.ts
export function cleanSlug(value: unknown): string | null;        // null unless ^[a-z0-9-]{1,40}$
// lib/session.ts
export const SESSION_COOKIE = "session";
export function sessionCookieHeader(value: string, expiresAt: string, siteEnv: string): string;
export function clearSessionCookieHeader(siteEnv: string): string;
export function readSessionCookie(cookieHeader: string | null): string | null;
// lib/same-origin.ts
export function isSameOrigin(request: Request, siteOrigin: string): boolean;
// app/api/session/route.ts
export async function POST(request: Request): Promise<Response>;   // body { id_token: string, campaign: string | null }
export async function DELETE(request: Request): Promise<Response>;
```

- `isSameOrigin`: true when the `Origin` header equals `siteOrigin`; when there is no `Origin` header, true only if `Sec-Fetch-Site` is `same-origin`; false otherwise.
- `POST /api/session` answers: 200 `{ "next": "/welcome" }`, or `{ "next": "/welcome?check=started" }` when `join.check` is `started`, with the `Set-Cookie` header; 400 `{ "error": "validation_failed" }` when `id_token` is not a non-empty string; 401 `{ "error": "unauthenticated" }`; 403 `{ "error": "forbidden" }` when not same-origin; 503 `{ "error": "unavailable" }`. No cookie on any answer except 200. The id token is never logged or echoed.
- `DELETE /api/session`: same-origin check; calls `revokeSession` if a cookie is present, ignoring its failure; always clears the cookie; 204.
- Route handlers read `SITE_ORIGIN` and `SITE_ENV` from `process.env` at call time.

- [ ] **Step 1: Write the failing tests**

```ts
// apps/web/tests/session-route.test.ts
// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakePlatformApi } from "@/lib/platform-api/fake";
import { cleanSlug } from "@/lib/slug";
import { isSameOrigin } from "@/lib/same-origin";
import { readSessionCookie, sessionCookieHeader } from "@/lib/session";

const fake = new FakePlatformApi();
vi.mock("@/lib/platform-api/client", async (original) => ({
  ...(await original<typeof import("@/lib/platform-api/client")>()),
  getPlatformApi: () => fake,
}));
import { DELETE, POST } from "@/app/api/session/route";

const ORIGIN = "https://dev.example.org";
const post = (body: unknown, headers: Record<string, string> = { origin: ORIGIN }) =>
  POST(new Request(`${ORIGIN}/api/session`, { method: "POST", headers, body: JSON.stringify(body) }));

beforeEach(() => {
  process.env.SITE_ORIGIN = ORIGIN;
  process.env.SITE_ENV = "dev";
});

describe("cleanSlug", () => {
  it.each([["founding", "founding"], ["a-1", "a-1"]])("keeps %s", (input, output) => {
    expect(cleanSlug(input)).toBe(output);
  });
  it.each(["../admin", "Founding", "", "a".repeat(41), "<b>", 7, null, undefined])("drops %s", (input) => {
    expect(cleanSlug(input)).toBeNull();
  });
});

describe("isSameOrigin", () => {
  const req = (headers: Record<string, string>) => new Request(`${ORIGIN}/api/x`, { method: "POST", headers });
  it("accepts the site's own origin", () => expect(isSameOrigin(req({ origin: ORIGIN }), ORIGIN)).toBe(true));
  it("refuses another origin", () => expect(isSameOrigin(req({ origin: "https://evil.example" }), ORIGIN)).toBe(false));
  it("accepts same-origin fetch metadata when Origin is absent", () =>
    expect(isSameOrigin(req({ "sec-fetch-site": "same-origin" }), ORIGIN)).toBe(true));
  it("refuses when both are absent", () => expect(isSameOrigin(req({}), ORIGIN)).toBe(false));
});

describe("session cookie", () => {
  it("is http-only, lax, secure outside local, and expires when the session does", () => {
    const header = sessionCookieHeader("abc", "2026-12-01T00:00:00Z", "dev");
    expect(header).toContain("session=abc");
    expect(header).toContain("HttpOnly");
    expect(header).toContain("SameSite=Lax");
    expect(header).toContain("Path=/");
    expect(header).toContain("Secure");
    expect(header).toContain("Expires=Tue, 01 Dec 2026 00:00:00 GMT");
    expect(sessionCookieHeader("abc", "2026-12-01T00:00:00Z", "local")).not.toContain("Secure");
  });
  it("is read back from a cookie header", () => {
    expect(readSessionCookie("a=1; session=abc; b=2")).toBe("abc");
    expect(readSessionCookie(null)).toBeNull();
  });
});

describe("POST /api/session", () => {
  it("sets the cookie and sends a recognised reader to the welcome page", async () => {
    const res = await post({ id_token: "fake-token:ana", campaign: "founding" });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ next: "/welcome" });
    expect(res.headers.get("set-cookie")).toContain("session=fake-session:ana");
  });
  it("drops a slug that is not a slug", async () => {
    const spy = vi.spyOn(fake, "resolveSession");
    await post({ id_token: "fake-token:bo", campaign: "../admin" });
    expect(spy).toHaveBeenLastCalledWith("fake-token:bo", null);
  });
  it("refuses another origin and sets no cookie", async () => {
    const res = await post({ id_token: "fake-token:ana", campaign: null }, { origin: "https://evil.example" });
    expect(res.status).toBe(403);
    expect(res.headers.get("set-cookie")).toBeNull();
  });
  it("answers 400 without a token", async () => {
    expect((await post({ campaign: null })).status).toBe(400);
  });
  it("answers 401 for a token the service rejects", async () => {
    const res = await post({ id_token: "nonsense", campaign: null });
    expect(res.status).toBe(401);
    expect(res.headers.get("set-cookie")).toBeNull();
  });
  it("answers 503 and sets no cookie when the service cannot be reached", async () => {
    fake.failNext("unavailable");
    const res = await post({ id_token: "fake-token:ana", campaign: null });
    expect(res.status).toBe(503);
    expect(res.headers.get("set-cookie")).toBeNull();
  });
  it("never puts the token in the answer", async () => {
    const res = await post({ id_token: "nonsense-token-value", campaign: null });
    expect(await res.text()).not.toContain("nonsense-token-value");
  });
});

describe("DELETE /api/session", () => {
  it("clears the cookie even when revoking fails", async () => {
    fake.failNext("unavailable");
    const res = await DELETE(
      new Request(`${ORIGIN}/api/session`, { method: "DELETE", headers: { origin: ORIGIN, cookie: "session=fake-session:bo" } }),
    );
    expect(res.status).toBe(204);
    expect(res.headers.get("set-cookie")).toContain("session=;");
  });
});
```

- [ ] **Step 2: See them fail**

Run: `npm test -- session-route`
Expected: FAIL, cannot resolve `@/lib/slug`.

- [ ] **Step 3: Implement the three helpers and the route**

The route builds its `Response` by hand and sets the `Set-Cookie` header itself, so it can be called in a test with a plain `Request`. It does not import `next/headers`. If the test runner objects to the mock factory reading `fake` before it is defined, create the fake with `vi.hoisted`; the assertions stay as written.

- [ ] **Step 4: See them pass**

Run: `npm test && npm run typecheck`
Expected: all tests pass; no type errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: session cookie, same-origin check and the session route"
```

---

### Task 3: The sign-in client

**Files:**
- Create: `apps/web/lib/identity/auth-client.ts`, `lib/identity/config.ts`, `tests/auth-client.test.ts`

**Interfaces:**
- Produces:

```ts
// lib/identity/auth-client.ts
export type AuthErrorCode = "invalid_email" | "link_expired" | "link_used" | "popup_closed" | "network" | "unknown";
export class AuthError extends Error { constructor(readonly code: AuthErrorCode); }
export interface AuthClient {
  sendEmailLink(email: string, continueUrl: string): Promise<void>;
  isEmailLink(href: string): boolean;
  completeEmailLink(email: string, href: string): Promise<string>;   // resolves to an ID token
  signInWithGoogle(): Promise<string>;                                // resolves to an ID token
}
export function toAuthError(error: unknown): AuthError;
export function createFirebaseAuthClient(config: { apiKey: string; authDomain: string }): AuthClient;
export function createFakeAuthClient(): AuthClient;
// lib/identity/config.ts
export type IdentityConfig = { kind: "firebase"; apiKey: string; authDomain: string } | { kind: "fake" } | { kind: "missing" };
export function identityConfig(env?: Record<string, string | undefined>): IdentityConfig;
```

- `toAuthError` maps the SDK's error codes: `auth/invalid-email` → `invalid_email`; `auth/expired-action-code` → `link_expired`; `auth/invalid-action-code` → `link_used`; `auth/popup-closed-by-user` and `auth/cancelled-popup-request` → `popup_closed`; `auth/network-request-failed` → `network`; anything else → `unknown`.
- `createFirebaseAuthClient`: initialises one app, uses `inMemoryPersistence`, and after every successful sign-in takes the ID token and then signs the SDK out, so no refresh token stays in the browser. `sendEmailLink` passes `{ url: continueUrl, handleCodeInApp: true }`.
- `createFakeAuthClient`: `completeEmailLink(email)` and `signInWithGoogle()` resolve to `fake-token:<part of the email before @>` (Google: `fake-token:bo`); `isEmailLink(href)` is true when the URL has an `oobCode` parameter; an `oobCode` of `expired` rejects with `link_expired`, `used` with `link_used`.
- `identityConfig`: `fake` when `PLATFORM_API_FAKE` is `"1"` and `SITE_ENV` is not `prod`; `firebase` when both `IDENTITY_API_KEY` and `IDENTITY_AUTH_DOMAIN` are set; otherwise `missing`.

- [ ] **Step 1: Write the failing tests**

```ts
// apps/web/tests/auth-client.test.ts
import { describe, expect, it } from "vitest";
import { createFakeAuthClient, toAuthError } from "@/lib/identity/auth-client";
import { identityConfig } from "@/lib/identity/config";

describe("toAuthError", () => {
  it.each([
    ["auth/invalid-email", "invalid_email"],
    ["auth/expired-action-code", "link_expired"],
    ["auth/invalid-action-code", "link_used"],
    ["auth/popup-closed-by-user", "popup_closed"],
    ["auth/cancelled-popup-request", "popup_closed"],
    ["auth/network-request-failed", "network"],
    ["auth/something-new", "unknown"],
  ])("maps %s to %s", (sdkCode, code) => {
    expect(toAuthError({ code: sdkCode }).code).toBe(code);
  });
  it("maps anything that is not an SDK error to unknown", () => {
    expect(toAuthError(new Error("boom")).code).toBe("unknown");
  });
});

describe("fake auth client", () => {
  const client = createFakeAuthClient();
  it("recognises a link by its code", () => {
    expect(client.isEmailLink("https://dev.example.org/auth/finish?oobCode=ok")).toBe(true);
    expect(client.isEmailLink("https://dev.example.org/auth/finish")).toBe(false);
  });
  it("turns an email into a fake token", async () => {
    await expect(client.completeEmailLink("ana@example.org", "https://x/auth/finish?oobCode=ok")).resolves.toBe("fake-token:ana");
  });
  it("fails an expired and a used link the way the real one does", async () => {
    await expect(client.completeEmailLink("ana@example.org", "https://x/?oobCode=expired")).rejects.toMatchObject({ code: "link_expired" });
    await expect(client.completeEmailLink("ana@example.org", "https://x/?oobCode=used")).rejects.toMatchObject({ code: "link_used" });
  });
});

describe("identityConfig", () => {
  it("is fake only outside prod", () => {
    expect(identityConfig({ PLATFORM_API_FAKE: "1", SITE_ENV: "local" })).toEqual({ kind: "fake" });
    expect(identityConfig({ PLATFORM_API_FAKE: "1", SITE_ENV: "prod" })).toEqual({ kind: "missing" });
  });
  it("needs both values", () => {
    expect(identityConfig({ IDENTITY_API_KEY: "k", IDENTITY_AUTH_DOMAIN: "d.example" })).toEqual({ kind: "firebase", apiKey: "k", authDomain: "d.example" });
    expect(identityConfig({ IDENTITY_API_KEY: "k" })).toEqual({ kind: "missing" });
  });
});
```

- [ ] **Step 2: See them fail**

Run: `npm test -- auth-client`
Expected: FAIL, cannot resolve `@/lib/identity/auth-client`.

- [ ] **Step 3: Implement both files**

`auth-client.ts` starts with `"use client"` only if the bundler requires it for the SDK import; the file must stay importable in a jsdom test. Import the SDK lazily inside `createFirebaseAuthClient` so the fake and `toAuthError` load without it.

- [ ] **Step 4: See them pass**

Run: `npm test && npm run typecheck && npm run build`
Expected: all tests pass; the build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: sign-in client wrapper with a fake for tests and local work"
```

---

### Task 4: The join page

**Files:**
- Create: `apps/web/app/join/page.tsx`, `app/join/[slug]/page.tsx`, `app/join/JoinScreen.tsx`, `tests/join-screen.test.tsx`

**Interfaces:**
- Consumes: `getPlatformApi().campaign`, `cleanSlug`, `identityConfig`, `AuthClient`, `readSessionCookie`.
- Produces:

```ts
// app/join/JoinScreen.tsx  ("use client")
export type JoinScreenProps = {
  campaign: Campaign;
  slug: string | null;
  siteOrigin: string;
  senderHint: string | null;
  identity: IdentityConfig;
  authClient?: AuthClient;                                             // tests pass a fake
  postSession?: (idToken: string, campaign: string | null) => Promise<{ next: string }>;
  navigate?: (url: string) => void;
};
export function JoinScreen(props: JoinScreenProps): React.JSX.Element;
export function continueUrl(siteOrigin: string, slug: string | null): string;   // "<origin>/auth/finish" or "<origin>/auth/finish?c=<slug>"
```

- Both pages are server components: clean the slug, fetch the campaign, and redirect to `/welcome` only when a `session` cookie is present **and** `me()` succeeds with it; if `me()` fails with `unauthenticated`, render `JoinScreen` (the finish step replaces the stale cookie). Redirecting on the cookie alone would loop forever with `/welcome` for a revoked cookie. Otherwise render `JoinScreen`. The form carries `noValidate`, so the app's own message "Check the email address." is shown instead of the browser's. If the campaign call fails with `unavailable`, render the screen with a closed campaign.
- `JoinScreen` behaviour:
  - Campaign state other than `open`: the heading "Opening soon", the campaign's body text, no form and no button.
  - Open: the campaign's headline (a heading) and body; an email field labelled "Email address" and the button "Email me a sign-in link"; the button "Continue with Google"; a link "Terms" to `/terms` and a link "Privacy notice" to `/privacy`.
  - `JoinScreen` renders only the join content. The pages wrap it in the site's `Header` and `Footer`.
  - Sending a link: trims the address; refuses an address without `@` with the message "Check the email address."; stores the address in `localStorage["signin.email"]`; calls `sendEmailLink(email, continueUrl(siteOrigin, slug))`; then shows "Check your inbox." followed, when `senderHint` is set, by "The email comes from {senderHint}.", then "If it is not there after a minute, look in the spam folder or use Continue with Google.", and the button "Use a different email".
  - Google: `signInWithGoogle()` → `postSession(token, slug)` → `navigate(next)`. `popup_closed` returns silently to the idle state.
  - Any other failure: "Something went wrong. Try again." in the live region. The form stays usable.
  - `identity.kind` is `missing`: the text "Sign-in is not set up in this environment." and no form.

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/web/tests/join-screen.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { JoinScreen, continueUrl } from "@/app/join/JoinScreen";
import { AuthError, type AuthClient } from "@/lib/identity/auth-client";
import type { Campaign } from "@/lib/platform-api/types";

const open: Campaign = { slug: "founding", audience: "substack_paid", state: "open", copy: { headline: "Welcome, subscribers", body: "Sign in with the email you use for the newsletter.", cta: "Sign in" } };
const authClient = (over: Partial<AuthClient> = {}): AuthClient => ({
  sendEmailLink: vi.fn().mockResolvedValue(undefined),
  isEmailLink: () => false,
  completeEmailLink: vi.fn(),
  signInWithGoogle: vi.fn().mockResolvedValue("fake-token:bo"),
  ...over,
});
const setup = (props: Partial<Parameters<typeof JoinScreen>[0]> = {}) => {
  const client = props.authClient ?? authClient();
  const postSession = vi.fn().mockResolvedValue({ next: "/welcome" });
  const navigate = vi.fn();
  render(<JoinScreen campaign={open} slug="founding" siteOrigin="https://dev.example.org" senderHint="signin@dev.example.org"
    identity={{ kind: "fake" }} authClient={client} postSession={postSession} navigate={navigate} {...props} />);
  return { client, postSession, navigate, user: userEvent.setup() };
};

beforeEach(() => localStorage.clear());

describe("continueUrl", () => {
  it("carries the slug", () => expect(continueUrl("https://dev.example.org", "founding")).toBe("https://dev.example.org/auth/finish?c=founding"));
  it("has no query without a slug", () => expect(continueUrl("https://dev.example.org", null)).toBe("https://dev.example.org/auth/finish"));
});

describe("JoinScreen", () => {
  it("shows the campaign's words and both ways to sign in", () => {
    setup();
    expect(screen.getByRole("heading", { name: "Welcome, subscribers" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Email me a sign-in link" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy notice" })).toHaveAttribute("href", "/privacy");
  });

  it("sends the link with the slug in the return address and remembers the email", async () => {
    const { client, user } = setup();
    await user.type(screen.getByLabelText("Email address"), "  ana@example.org ");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    expect(client.sendEmailLink).toHaveBeenCalledWith("ana@example.org", "https://dev.example.org/auth/finish?c=founding");
    expect(localStorage.getItem("signin.email")).toBe("ana@example.org");
    expect(await screen.findByText("Check your inbox.")).toBeInTheDocument();
    expect(screen.getByText("The email comes from signin@dev.example.org.")).toBeInTheDocument();
  });

  it("refuses an address without an at sign and sends nothing", async () => {
    const { client, user } = setup();
    await user.type(screen.getByLabelText("Email address"), "ana");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    expect(client.sendEmailLink).not.toHaveBeenCalled();
    expect(screen.getByText("Check the email address.")).toBeInTheDocument();
  });

  it("signs in with Google and goes where the server says", async () => {
    const { postSession, navigate, user } = setup();
    await user.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(postSession).toHaveBeenCalledWith("fake-token:bo", "founding");
    expect(navigate).toHaveBeenCalledWith("/welcome");
  });

  it("stays quiet when the Google window is closed", async () => {
    const { postSession, user } = setup({ authClient: authClient({ signInWithGoogle: vi.fn().mockRejectedValue(new AuthError("popup_closed")) }) });
    await user.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(postSession).not.toHaveBeenCalled();
    expect(screen.queryByText("Something went wrong. Try again.")).not.toBeInTheDocument();
  });

  it("says so when sending fails and keeps the form", async () => {
    const { user } = setup({ authClient: authClient({ sendEmailLink: vi.fn().mockRejectedValue(new AuthError("network")) }) });
    await user.type(screen.getByLabelText("Email address"), "ana@example.org");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    expect(await screen.findByText("Something went wrong. Try again.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
  });

  it("offers nothing to press when the campaign is not open", () => {
    setup({ campaign: { ...open, state: "closed" } });
    expect(screen.getByRole("heading", { name: "Opening soon" })).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("explains itself when sign-in is not configured", () => {
    setup({ identity: { kind: "missing" } });
    expect(screen.getByText("Sign-in is not set up in this environment.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: See them fail**

Run: `npm test -- join-screen`
Expected: FAIL, cannot resolve `@/app/join/JoinScreen`.

- [ ] **Step 3: Implement `JoinScreen` and the two pages**

Use the site's existing classes from `app/globals.css` (`button`, `button-primary`, `section-kicker`) and the existing `Header` and `Footer` components. The default `postSession` is a `fetch("/api/session", { method: "POST", ... })` that throws on a non-200 answer; the default `navigate` is `window.location.assign`. `app/join/page.tsx` renders the same thing as `[slug]/page.tsx` with a null slug.

- [ ] **Step 4: See them pass**

Run: `npm test && npm run typecheck && npm run build`
Expected: all tests pass; the build lists `/join` and `/join/[slug]` as dynamic routes.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: join page with emailed link and Google sign-in"
```

---

### Task 5: Completing the emailed link

**Files:**
- Create: `apps/web/app/auth/finish/page.tsx`, `app/auth/finish/FinishSignIn.tsx`, `tests/finish-sign-in.test.tsx`

**Interfaces:**
- Consumes: `AuthClient`, `AuthError`, `cleanSlug`, `identityConfig`.
- Produces:

```ts
// app/auth/finish/FinishSignIn.tsx  ("use client")
export type FinishProps = {
  identity: IdentityConfig;
  href?: string;                                   // tests pass it; default window.location.href
  authClient?: AuthClient;
  postSession?: (idToken: string, campaign: string | null) => Promise<{ next: string }>;
  navigate?: (url: string) => void;
};
export function FinishSignIn(props: FinishProps): React.JSX.Element;
export function slugFromHref(href: string): string | null;
```

- `slugFromHref`: the cleaned `c` parameter of the URL; if absent, the cleaned `c` parameter of the URL found in its `continueUrl` parameter; otherwise null.
- Behaviour:
  - The address is not a sign-in link: "This page finishes a sign-in link." and a link "Start again" to `/join`.
  - A link and a stored email: the text "Signing you in." while it completes, then `postSession(token, slugFromHref(href))`, then `localStorage.removeItem("signin.email")`, then `navigate(next)`.
  - A link and no stored email: a labelled field "Email address" with the text "Type the email address the link was sent to." and the button "Finish signing in".
  - `link_expired` or `link_used`: "This link has expired or was already used." and a link "Send me a new link" to `/join/<slug>` (or `/join`).
  - `postSession` fails: "We could not reach the service. Try again." and the button "Try again", which calls `postSession` again with the **same** token; it does not ask for a new link.

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/web/tests/finish-sign-in.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FinishSignIn, slugFromHref } from "@/app/auth/finish/FinishSignIn";
import { createFakeAuthClient } from "@/lib/identity/auth-client";

const LINK = "https://dev.example.org/auth/finish?c=founding&oobCode=ok&mode=signIn";
const setup = (href: string, postSession = vi.fn().mockResolvedValue({ next: "/welcome" })) => {
  const navigate = vi.fn();
  render(<FinishSignIn identity={{ kind: "fake" }} href={href} authClient={createFakeAuthClient()} postSession={postSession} navigate={navigate} />);
  return { postSession, navigate, user: userEvent.setup() };
};

beforeEach(() => localStorage.clear());

describe("slugFromHref", () => {
  it("reads c from the address", () => expect(slugFromHref(LINK)).toBe("founding"));
  it("reads c from the continue address when the link was opened directly", () =>
    expect(slugFromHref("https://dev.example.org/auth/finish?oobCode=ok&continueUrl=" + encodeURIComponent("https://dev.example.org/auth/finish?c=founding"))).toBe("founding"));
  it("drops what is not a slug", () => expect(slugFromHref("https://dev.example.org/auth/finish?c=../admin&oobCode=ok")).toBeNull());
});

describe("FinishSignIn", () => {
  it("completes with the stored email, forgets it, and moves on", async () => {
    localStorage.setItem("signin.email", "ana@example.org");
    const { postSession, navigate } = setup(LINK);
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("/welcome"));
    expect(postSession).toHaveBeenCalledWith("fake-token:ana", "founding");
    expect(localStorage.getItem("signin.email")).toBeNull();
  });

  it("asks for the email on another device, then completes", async () => {
    const { postSession, navigate, user } = setup(LINK);
    expect(screen.getByText("Type the email address the link was sent to.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Email address"), "ana@example.org");
    await user.click(screen.getByRole("button", { name: "Finish signing in" }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("/welcome"));
    expect(postSession).toHaveBeenCalledWith("fake-token:ana", "founding");
  });

  it.each(["expired", "used"])("explains a link that is %s and offers a new one for the same campaign", async (code) => {
    localStorage.setItem("signin.email", "ana@example.org");
    const { postSession } = setup(`https://dev.example.org/auth/finish?c=founding&oobCode=${code}`);
    expect(await screen.findByText("This link has expired or was already used.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Send me a new link" })).toHaveAttribute("href", "/join/founding");
    expect(postSession).not.toHaveBeenCalled();
  });

  it("retries with the same token when the service was unreachable", async () => {
    localStorage.setItem("signin.email", "ana@example.org");
    const postSession = vi.fn().mockRejectedValueOnce(new Error("503")).mockResolvedValueOnce({ next: "/welcome" });
    const { navigate, user } = setup(LINK, postSession);
    expect(await screen.findByText("We could not reach the service. Try again.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("/welcome"));
    expect(postSession).toHaveBeenNthCalledWith(2, "fake-token:ana", "founding");
  });

  it("says what the page is for when opened without a link", () => {
    setup("https://dev.example.org/auth/finish");
    expect(screen.getByText("This page finishes a sign-in link.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start again" })).toHaveAttribute("href", "/join");
  });
});
```

- [ ] **Step 2: See them fail**

Run: `npm test -- finish-sign-in`
Expected: FAIL, cannot resolve `@/app/auth/finish/FinishSignIn`.

- [ ] **Step 3: Implement the component and the page**

The page is a server component that passes `identityConfig()` to `FinishSignIn` and sets `robots: { index: false }` in its metadata. The component keeps the token in component state only.

- [ ] **Step 4: See them pass**

Run: `npm test && npm run typecheck && npm run build`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: finish page for the emailed sign-in link"
```

---

### Task 6: Welcome page, terms step and the not-recognised route

**Files:**
- Create: `apps/web/lib/welcome.ts`, `app/welcome/page.tsx`, `app/welcome/TermsStep.tsx`, `app/welcome/NotRecognised.tsx`, `app/api/terms/route.ts`, `app/api/support/route.ts`, `app/terms/page.tsx`, `app/privacy/page.tsx`, `tests/welcome.test.tsx`, `tests/terms-route.test.ts`

**Interfaces:**
- Consumes: `PlatformApi.me`, `acceptTerms`, `supportRequest`; `readSessionCookie`; `isSameOrigin`.
- Produces:

```ts
// lib/welcome.ts
export type WelcomeView =
  | { kind: "terms" }
  | { kind: "paid"; grantUntil: string | null; includedWhilePaying: boolean }
  | { kind: "free"; checking: boolean };
export function welcomeView(me: { member: Member; access: Access }, check: string | null): WelcomeView;
// app/api/terms/route.ts
export async function POST(request: Request): Promise<Response>;     // no body
// app/api/support/route.ts
export async function POST(request: Request): Promise<Response>;     // body { note: string }
```

- `welcomeView`: `terms` when `member.terms.accepted` is false. Otherwise `paid` when `access.tier` is `paid`: `grantUntil` is the latest `valid_until` among reasons with label `launch_grant` and status `active`, or null; `includedWhilePaying` is true when a reason with label `substack_subscription` has status `active` or `grace`. Otherwise `free`, with `checking` true only when `check` is `"started"`.
- `POST /api/terms`: same-origin check (403); no session cookie (401); reads `me`, then calls `acceptTerms` with `member.terms.required.terms_version` and `.privacy_version`; 200 `{ "ok": true }`; 503 when the service cannot be reached.
- `POST /api/support`: same-origin; session required; `note` trimmed and cut to 500 characters; sends kind `paid_not_recognised`; 200 `{ "ok": true }`; when the service answers `terms_required`, 409 `{ "error": "terms_required" }` and `NotRecognised` shows "Accept the terms first." The note is not logged. The route's tests sign the person in and accept the terms inside each test; they do not rely on an earlier test, and one test checks the 409.
- `app/welcome/page.tsx` (server): no session cookie → redirect to `/join`; `me` fails with `unauthenticated` → redirect to `/join`; otherwise render by view:

| View | The page shows |
| --- | --- |
| `terms` | Heading "Before you start". A check box labelled "I have read and accept the terms and the privacy notice", with both words linked. The button "Continue", disabled until the box is ticked; it posts to `/api/terms` and reloads the page |
| `paid` | Heading "You are recognised as a paid subscriber." When `includedWhilePaying`: "Your membership is included for as long as your subscription is active." When `grantUntil` is set: "Your access is guaranteed until {date}." with the date written as day, month name and year. A link "Open your workspace" to `/member` |
| `free` | Heading "You are in as a free member." When `checking`: "We are checking your subscription. This can take a minute." and a link "Check again" to `/welcome`. A link "See how to upgrade" to `/upgrade` (built in Wave 2). Then `NotRecognised` |

- `NotRecognised`: heading "Paying on Substack already?"; the sentence "Sign in with the email address your newsletter arrives at."; a link "Sign in with another email" that posts `DELETE /api/session` and goes to `/join`; a labelled text area "Tell us what happened" (limit 500 characters) and the button "Send", which posts to `/api/support` and then shows "Thank you. We will look at it."
- `/terms` and `/privacy`: each a page with its title and the sentence "This text is published before the platform opens.", `robots: { index: false }`. Task W6 replaces them with the owner's approved texts.

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/web/tests/welcome.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TermsStep } from "@/app/welcome/TermsStep";
import { NotRecognised } from "@/app/welcome/NotRecognised";
import { FakePlatformApi } from "@/lib/platform-api/fake";
import { welcomeView } from "@/lib/welcome";

const meOf = async (name: string, accept = true) => {
  const api = new FakePlatformApi();
  const { session } = await api.resolveSession(`fake-token:${name}`, null);
  if (accept) await api.acceptTerms(session.cookie, "t1", "p1");
  return api.me(session.cookie);
};

describe("welcomeView", () => {
  it("asks for the terms first", async () => expect(welcomeView(await meOf("ana", false), null)).toEqual({ kind: "terms" }));
  it("shows ana as paid, included while paying, with a guarantee date", async () => {
    const view = welcomeView(await meOf("ana"), null);
    expect(view).toMatchObject({ kind: "paid", includedWhilePaying: true });
    expect(view.kind === "paid" && view.grantUntil).toBeTruthy();
  });
  it("shows fay as paid through the grant alone", async () =>
    expect(welcomeView(await meOf("fay"), null)).toMatchObject({ kind: "paid", includedWhilePaying: false }));
  it("shows hal as paid with no guarantee date", async () =>
    expect(welcomeView(await meOf("hal"), null)).toEqual({ kind: "paid", grantUntil: null, includedWhilePaying: true }));
  it("shows bo as free, checking only when a check was started", async () => {
    expect(welcomeView(await meOf("bo"), null)).toEqual({ kind: "free", checking: false });
    expect(welcomeView(await meOf("bo"), "started")).toEqual({ kind: "free", checking: true });
    expect(welcomeView(await meOf("bo"), "anything-else")).toEqual({ kind: "free", checking: false });
  });
});

describe("TermsStep", () => {
  it("keeps Continue disabled until the box is ticked, then accepts", async () => {
    const accept = vi.fn().mockResolvedValue(undefined);
    render(<TermsStep accept={accept} />);
    const button = screen.getByRole("button", { name: "Continue" });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(button);
    expect(accept).toHaveBeenCalledOnce();
  });
});

describe("NotRecognised", () => {
  it("sends the note and thanks the member", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    render(<NotRecognised send={send} />);
    await userEvent.type(screen.getByLabelText("Tell us what happened"), "I pay yearly with another address");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(send).toHaveBeenCalledWith("I pay yearly with another address");
    expect(await screen.findByText("Thank you. We will look at it.")).toBeInTheDocument();
  });
});
```

```ts
// apps/web/tests/terms-route.test.ts
// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const fake = new FakePlatformApi();
vi.mock("@/lib/platform-api/client", async (original) => ({
  ...(await original<typeof import("@/lib/platform-api/client")>()),
  getPlatformApi: () => fake,
}));
import { POST as acceptTerms } from "@/app/api/terms/route";
import { POST as support } from "@/app/api/support/route";

const ORIGIN = "https://dev.example.org";
const req = (path: string, headers: Record<string, string>, body?: unknown) =>
  new Request(`${ORIGIN}${path}`, { method: "POST", headers, body: body ? JSON.stringify(body) : undefined });

beforeEach(async () => {
  process.env.SITE_ORIGIN = ORIGIN;
  process.env.SITE_ENV = "dev";
  await fake.resolveSession("fake-token:bo", null);
});

describe("POST /api/terms", () => {
  it("accepts the versions the service requires", async () => {
    const res = await acceptTerms(req("/api/terms", { origin: ORIGIN, cookie: "session=fake-session:bo" }));
    expect(res.status).toBe(200);
    expect((await fake.me("fake-session:bo")).member.terms.accepted).toBe(true);
  });
  it("refuses another origin", async () =>
    expect((await acceptTerms(req("/api/terms", { origin: "https://evil.example", cookie: "session=fake-session:bo" }))).status).toBe(403));
  it("refuses a visitor without a session", async () =>
    expect((await acceptTerms(req("/api/terms", { origin: ORIGIN }))).status).toBe(401));
});

describe("POST /api/support", () => {
  it("cuts the note to 500 characters and files it as paid_not_recognised", async () => {
    const spy = vi.spyOn(fake, "supportRequest");
    const res = await support(req("/api/support", { origin: ORIGIN, cookie: "session=fake-session:bo" }, { note: "x".repeat(600) }));
    expect(res.status).toBe(200);
    expect(spy).toHaveBeenCalledWith("fake-session:bo", "paid_not_recognised", "x".repeat(500));
  });
  it("refuses another origin", async () =>
    expect((await support(req("/api/support", { origin: "https://evil.example", cookie: "session=fake-session:bo" }, { note: "n" }))).status).toBe(403));
});
```

- [ ] **Step 2: See them fail**

Run: `npm test -- welcome terms-route`
Expected: FAIL, cannot resolve `@/lib/welcome`.

- [ ] **Step 3: Implement**

`TermsStep` takes `accept: () => Promise<void>` and `NotRecognised` takes `send: (note: string) => Promise<void>`, both with defaults that post to the routes above; the page passes nothing. The page reads the cookie with `cookies()` from `next/headers` and the `check` query parameter from `searchParams`. Dates are formatted with `Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })`.

- [ ] **Step 4: See them pass, and walk the journey by hand**

Run: `npm test && npm run typecheck && npm run build`
Expected: all tests pass.
Then: `PLATFORM_API_FAKE=1 SITE_ENV=local SITE_ORIGIN=http://localhost:3000 npm run dev`, open `/join/founding`, type `ana@example.org`, open `/auth/finish?c=founding&oobCode=ok` in the same browser, accept the terms.
Expected: the page says "You are recognised as a paid subscriber." with a guarantee date. Repeat with `bo@example.org`: "You are in as a free member."

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: welcome page with terms step and the not-recognised route"
```

---

## Exit test for this plan

1. `npm test`, `npm run typecheck` and `npm run build` pass in `apps/web`, locally and in CI.
2. With the fake switched on, the two journeys of Task 6, Step 4 work in a browser, by keyboard alone.
3. No file outside `apps/web/` changed, except through the one `cross-lane` pull request.
4. A search of the lane's diff finds no `NEXT_PUBLIC_`, no email address outside `example.org`, and no `console.log` of a token or an address.
