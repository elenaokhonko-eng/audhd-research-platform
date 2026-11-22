# Lane L2 Web · Workspace, Account, Upgrade, Library and Legal Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in member has a workspace: a navigation that shows what their access includes, an Account page that explains in plain words why they have that access, an upgrade page with the right route and the current offer, a library they can download from, and the terms and privacy notice they agreed to.

**Architecture:** Every page is rendered on the server and asks `platform-api` what the member may see; the browser is never trusted with that decision. One server helper, `requireMember`, guards every workspace page. What a page shows is computed by small pure functions in `lib/`, tested without a browser; components only display the result. As in the first wave, everything is built and tested against `FakePlatformApi`, which this plan extends, so the lane does not wait for the service.

**Tech Stack:** Next.js 16 (app router, standalone output), React 19, TypeScript strict, Vitest with Testing Library. One new dependency: `marked`, pinned to an exact version, to render the two legal texts.

**Spec:** [launch design](../specs/2026-11-19-launch-invites-grants-promotions-design.md) §5.5 and §5.6 · [contracts](../../contracts/stage-1-launch.md) §2 (routes and shapes), the refinements list in §3, the `web` settings in §6, the legal texts in §8 · [02](../../architecture/02-membership-and-entitlements.md) §2 (sections per tier) · [04](../../architecture/04-content-library-and-search.md) §2.2 · task cards W3 to W6.

**Lane rules:** change only `apps/web/`. Branch `web/workspace` from `integration/stage-1`; one draft pull request against it, kept up to date; mark it ready after Task 3 and again at the end (two pull requests), so the workspace shell can be tried on dev early. Do not change `content/legal/*.md`: the owner approved those texts.

## Global Constraints

- **The server decides.** A page under `/member` calls `requireMember` (and `requireSection` where a section is needed) before it renders anything. No component hides a link as its only protection.
- **Every POST route** follows `app/api/terms/route.ts`: refuse another origin (`isSameOrigin`), read the session with `readSessionCookie`, answer JSON with `cache-control: no-store`, map `unauthenticated` to 401 and anything unexpected to 503.
- **No address, name, cookie value or note** in a log line or an error message. Pages show `member.email_hint`, never an address.
- **Nothing about an offer is written in the code**: no percentage, no price, no date. The upgrade page and the banner display what `platform-api` returns.
- **Wording** is plain and specific; the exact sentences are in each task. Dates are shown as `23 November 2026` (`Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "UTC" })`).
- **Accessibility:** one `h1` per page; the current navigation link has `aria-current="page"`; a message that appears after an action is in an element with `role="status"` (or `role="alert"` for a refusal); every button and link has text.
- No tracking, no analytics, no third-party script. The privacy notice says so.
- Check command for every task, in `apps/web`: `npm run typecheck && npm test && npm run build`.

## Rulings by the integrator

1. **The Google button is shown only when `IDENTITY_GOOGLE_ENABLED` is `1`** (a new `web` setting; this plan's pull request adds it to the contracts page). The owner may store the Google sign-in client after launch; until then the button would only fail.
2. **Workspace addresses:** `/member` (overview), `/member/library`, `/member/research`, `/member/guides`, `/member/account`. `/upgrade` is outside the workspace shell so that a link to it works from any page.
3. **Research and Guides are views of the library catalogue**, filtered by kind: research = `meta_review`, `evidence_map`, `clinician_one_pager`; guides = `guide`, `worksheet`.
4. **A paid route typed by a free member redirects to `/upgrade`**; it does not answer 403 or 404.
5. **The legal pages render the Markdown files with `marked`.** The files are the repository's own and were approved by the owner, so their HTML is trusted; nothing a visitor typed is ever passed to `marked`.

## Review Focus

1. **A free member types `/member/research`.** Redirected to `/upgrade`, and nothing of the page is rendered. Pinned in Task 2.
2. **"Check again" never ends.** Polling stops after 60 seconds with a plain message. Pinned in Task 4.
3. **The service answers `rate_limited` or `unavailable`.** The page says so and keeps working; it never falls to the generic error page. Pinned in Tasks 4 and 5.
4. **A download link refused** (`paid_required`, `purchase_required`, too many downloads). The member is told why and where to go. Pinned in Task 5.
5. **A required terms version changes while a member is signed in.** Every workspace page sends them to `/welcome` to accept. Pinned in Task 2.

---

## File Structure

```
apps/web/
├─ lib/platform-api/types.ts client.ts fake.ts errors.ts     extended (Task 1)
├─ lib/member.ts            requireMember, requireSection, navFor                  (Task 2)
├─ lib/reasons.ts           reasonText, formatDate                                 (Task 3)
├─ lib/upgrade.ts           upgradeView, pollUntilPaid                             (Task 4)
├─ lib/library.ts           cardAction, viewOf, refusalText                        (Task 5)
├─ lib/legal.ts             readLegal                                              (Task 6)
├─ app/member/layout.tsx  page.tsx  account/page.tsx  library/page.tsx  library/[sku]/page.tsx  research/page.tsx  guides/page.tsx
├─ app/member/components/   WorkspaceNav.tsx, DeleteAccount.tsx, DownloadButton.tsx, ItemList.tsx
├─ app/upgrade/page.tsx  CheckAgain.tsx
├─ app/components/PromotionBanner.tsx
├─ app/terms/page.tsx  app/privacy/page.tsx                   replaced (Task 6)
├─ app/api/account/delete/route.ts  refresh-access/route.ts  tier/route.ts  library/[sku]/download/route.ts
└─ tests/  platform-api-wave2.test.ts  member.test.ts  reasons.test.ts  account.test.tsx  upgrade.test.tsx
           library.test.tsx  legal.test.ts  wave2-routes.test.ts
```

---

### Task 1: The client and the fake learn the second wave's routes

**Files:**
- Modify: `lib/platform-api/types.ts`, `errors.ts`, `client.ts`, `fake.ts`, `tests/fixtures/people.ts`
- Create: `tests/platform-api-wave2.test.ts`

**Interfaces:**
- Produces, in `types.ts` (shapes of contracts §2):

```ts
export interface Route { kind: "substack" | "platform_only" | "substack_change_plan"; available: boolean; url: string | null }
export interface Promotion { id: string; channel: string; plan_interval: "month" | "year" | null; starts_at: string; ends_at: string;
  url: string | null; display: { badge: string; headline: string; body: string } }
export interface UpgradeOptions { routes: Route[]; promotion: Promotion | null }
export interface RefreshTicket { check: "fresh" | "started" | "already_running"; last_completed_at: string | null; next_allowed_at: string }
export type ItemKind = "meta_review" | "evidence_map" | "clinician_one_pager" | "guide" | "worksheet";
export interface ItemCard { sku: string; title: string; kind: ItemKind; abstract: string; version: string; pages: number;
  access: "paid" | "free_members" | "purchase_only"; can_open: boolean; buy_url: string | null }
export interface ItemDetail { item: ItemCard; description: string; citation: string | null }
export interface SignedLink { url: string; expires_at: string }
```

- `ApiError` gains a fifth constructor argument `reason: "paid_required" | "purchase_required" | null = null`, read from `error.reason` of the response body.
- `PlatformApi` gains: `entitlements(session): Promise<Reason[]>`, `refreshAccess(session): Promise<RefreshTicket>`, `upgradeOptions(session): Promise<UpgradeOptions>`, `activePromotions(): Promise<Promotion[]>`, `libraryItems(session): Promise<ItemCard[]>`, `libraryItem(session, sku): Promise<ItemDetail>`, `download(session, sku): Promise<SignedLink>`, `requestDeletion(session): Promise<void>`. `HttpPlatformApi` implements each against the route of contracts §2 (`refreshAccess` accepts the 202).
- `FakePlatformApi` models them with invented data:
  - Items: `sample-map` (evidence_map, `paid`, buy URL `https://example.org/buy/sample-map`), `sample-guide` (guide, `free_members`), `sample-book` (guide, `purchase_only`, no buy URL). `can_open` follows the access rule for the member's tier and items. `libraryItems` returns them ordered by sku.
  - `access.sections` is `["overview", "library", "account"]` for the free tier and those plus `"research"` and `"guides"` for the paid tier (check what the first wave's fake returns and make it this).
  - `download`: allowed → `{ url: "https://files.invalid/<sku>", expires_at: now + 10 minutes }`; otherwise `ApiError(403, "forbidden", …, null, reason)`; unknown sku → 404.
  - `upgradeOptions`: as the Commerce plan's rule: paid → no routes; a member with a live `substack_status` reason → `substack_change_plan` to `https://example.org/subscribe` and no promotion; otherwise `substack` (to the promotion's URL when one is active, else `https://example.org/subscribe`) and `platform_only` unavailable.
  - `setPromotion(promotion | null)` switches the active promotion (default none). `activePromotions` returns it as a list.
  - `refreshAccess`: answers `started` and, after `upgradeAfterRefresh(name)` was called for that person, makes their tier `paid` on the next `me()`; a second call within the same test answers `already_running`.
  - `requestDeletion`: ends that person's sessions; `me` then fails with `unauthenticated`.
  - Every member route except the four of contracts §1 rejects with `terms_required` until the terms are accepted.

- [ ] **Step 1: Write the failing tests**

```ts
// tests/platform-api-wave2.test.ts
// @vitest-environment node
import { describe, expect, it } from "vitest";
import { HttpPlatformApi } from "@/lib/platform-api/client";
import { ApiError } from "@/lib/platform-api/errors";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const signedIn = async (name: string, accept = true) => {
  const api = new FakePlatformApi();
  const { session } = await api.resolveSession(`fake-token:${name}`, null);
  if (accept) await api.acceptTerms(session.cookie, "terms-v1", "privacy-v1");
  return { api, s: session.cookie };
};
const code = async (p: Promise<unknown>) => p.then(() => "ok", (e) => (e instanceof ApiError ? `${e.code}:${e.reason}` : "other"));

describe("FakePlatformApi, second wave", () => {
  it("shows a free member every card and what is locked", async () => {
    const { api, s } = await signedIn("bo");
    expect((await api.libraryItems(s)).map((i) => [i.sku, i.can_open])).toEqual([["sample-book", false], ["sample-guide", true], ["sample-map", false]]);
  });
  it("lets a paid member download and tells a free member why not", async () => {
    const ana = await signedIn("ana");
    expect((await ana.api.download(ana.s, "sample-map")).url).toBe("https://files.invalid/sample-map");
    const bo = await signedIn("bo");
    expect(await code(bo.api.download(bo.s, "sample-map"))).toBe("forbidden:paid_required");
    expect(await code(bo.api.download(bo.s, "sample-book"))).toBe("forbidden:purchase_required");
    expect(await code(bo.api.download(bo.s, "nope"))).toBe("not_found:null");
  });
  it("offers each kind of member the right upgrade route", async () => {
    const bo = await signedIn("bo");
    expect((await bo.api.upgradeOptions(bo.s)).routes.map((r) => [r.kind, r.available])).toEqual([["substack", true], ["platform_only", false]]);
    const hal = await signedIn("hal");
    expect(await hal.api.upgradeOptions(hal.s)).toEqual({ routes: [{ kind: "substack_change_plan", available: true, url: "https://example.org/subscribe" }], promotion: null });
    const ana = await signedIn("ana");
    expect(await ana.api.upgradeOptions(ana.s)).toEqual({ routes: [], promotion: null });
  });
  it("puts an active promotion on the free member's route only", async () => {
    const { api, s } = await signedIn("bo");
    api.setPromotion({ id: "p", channel: "substack_offer", plan_interval: "year", starts_at: "2026-01-01T00:00:00Z", ends_at: "2026-01-02T00:00:00Z",
      url: "https://example.org/offer", display: { badge: "b", headline: "h", body: "x" } });
    const options = await api.upgradeOptions(s);
    expect([options.routes[0].url, options.promotion?.id]).toEqual(["https://example.org/offer", "p"]);
    expect(await api.activePromotions()).toHaveLength(1);
  });
  it("turns a member paid after a refresh when the test says so", async () => {
    const { api, s } = await signedIn("bo");
    api.upgradeAfterRefresh("bo");
    expect((await api.refreshAccess(s)).check).toBe("started");
    expect((await api.me(s)).access.tier).toBe("paid");
    expect((await api.refreshAccess(s)).check).toBe("already_running");
  });
  it("asks for the terms on gated routes and ends the session on deletion", async () => {
    const { api, s } = await signedIn("bo", false);
    expect(await code(api.libraryItems(s))).toBe("terms_required:null");
    await api.requestDeletion(s);
    expect(await code(api.me(s))).toBe("unauthenticated:null");
  });
});

describe("HttpPlatformApi, second wave", () => {
  const respond = (status: number, body: unknown) => async () => new Response(JSON.stringify(body), { status });
  const api = (f: typeof fetch) => new HttpPlatformApi("https://api.example.org", async () => "tok", f);
  it("accepts 202 from refresh-access and reads the ticket", async () => {
    const ticket = { check: "started", last_completed_at: null, next_allowed_at: "2026-11-20T00:01:00Z" };
    expect(await api(respond(202, ticket) as typeof fetch).refreshAccess("s")).toEqual(ticket);
  });
  it("carries the reason of a refused download", async () => {
    const body = { error: { code: "forbidden", message: "Not included.", retry_after: null, reason: "paid_required" } };
    expect(await code(api(respond(403, body) as typeof fetch).download("s", "sample-map"))).toBe("forbidden:paid_required");
  });
  it("encodes the sku and sends the session header", async () => {
    let seen: Request | undefined;
    const f = (async (url: string, init: RequestInit) => { seen = new Request(url, init); return new Response(JSON.stringify({ item: {}, description: "", citation: null })); }) as unknown as typeof fetch;
    await api(f).libraryItem("s-1", "a/b");
    expect([seen?.url, seen?.headers.get("x-member-session")]).toEqual(["https://api.example.org/v1/library/items/a%2Fb", "s-1"]);
  });
});
```

- [ ] **Step 2: See them fail**

Run: `npm test -- tests/platform-api-wave2.test.ts`
Expected: FAIL, `api.libraryItems is not a function`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 9 new tests pass; every first-wave test still passes.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: API client and fake for entitlements, refresh, upgrade options, library and deletion"
```

---

### Task 2: The workspace shell and its guard

**Files:**
- Create: `lib/member.ts`, `app/member/layout.tsx`, `app/member/components/WorkspaceNav.tsx`, `tests/member.test.ts`
- Modify: `app/member/page.tsx` (replace the prototype page with the overview)

**Interfaces:**
- Produces, in `lib/member.ts`:

```ts
export type Section = "overview" | "library" | "research" | "guides" | "account";
export const SECTION_ROUTES: Record<Section, { href: string; label: string }>;   // /member, /member/library, …; labels "Overview", "Library", "Research", "Guides", "Account"
export function navFor(sections: string[]): { href: string; label: string }[];    // in the order of SECTION_ROUTES; unknown section names are ignored
export type Guard = { kind: "ok"; me: { member: Member; access: Access } } | { kind: "redirect"; to: string } | { kind: "unavailable" };
export async function guardMember(session: string | null, loadMe: (s: string) => Promise<{ member: Member; access: Access }>, section?: Section): Promise<Guard>;
export async function requireMember(section?: Section): Promise<{ member: Member; access: Access }>;   // reads the cookie, calls guardMember, redirects
```

- `guardMember`: no session → redirect `/join`; `loadMe` fails with `unauthenticated` → `/join`; any other failure → `unavailable`; terms not accepted → `/welcome`; a `section` not in `access.sections` → `/upgrade`; otherwise `ok`.
- `requireMember` turns `redirect` into Next's `redirect()` and `unavailable` into a thrown `Error("unavailable")`, which `app/member/error.tsx` (create it) shows as "The member area cannot be reached right now. Please try again in a minute." with a "Try again" button.
- `app/member/layout.tsx` calls `requireMember()`, renders `WorkspaceNav` from `navFor(access.sections)`, the member's `email_hint`, a sign-out button (the existing `SignOutButton`) and, when the tier is `free`, a link "Upgrade" to `/upgrade`. It exports `dynamic = "force-dynamic"` and `metadata.robots = { index: false }`.
- `/member` (overview): heading "Your workspace"; one sentence by tier ("You have full access." or "You have the free workspace."); links to the sections the member has.

- [ ] **Step 1: Write the failing tests**

```ts
// tests/member.test.ts
// @vitest-environment node
import { describe, expect, it } from "vitest";
import { guardMember, navFor } from "@/lib/member";
import { ApiError } from "@/lib/platform-api/errors";
import { FakePlatformApi } from "@/lib/platform-api/fake";

const world = async (name: string, accept = true) => {
  const api = new FakePlatformApi();
  const { session } = await api.resolveSession(`fake-token:${name}`, null);
  if (accept) await api.acceptTerms(session.cookie, "terms-v1", "privacy-v1");
  return { load: (s: string) => api.me(s), s: session.cookie };
};

describe("navFor", () => {
  it("lists a free member's sections in a fixed order", () =>
    expect(navFor(["account", "library", "overview"]).map((n) => n.href)).toEqual(["/member", "/member/library", "/member/account"]));
  it("adds research and guides for a paid member and ignores names it does not know", () =>
    expect(navFor(["overview", "library", "account", "research", "guides", "ask"]).map((n) => n.label)).toEqual(["Overview", "Library", "Research", "Guides", "Account"]));
});

describe("guardMember", () => {
  it("lets a member with accepted terms in", async () => {
    const { load, s } = await world("ana");
    expect((await guardMember(s, load, "research")).kind).toBe("ok");
  });
  it("sends a visitor without a session, or with a dead one, to sign in", async () => {
    const { load } = await world("ana");
    expect(await guardMember(null, load)).toEqual({ kind: "redirect", to: "/join" });
    expect(await guardMember("fake-session:nobody", load)).toEqual({ kind: "redirect", to: "/join" });
  });
  it("sends a member who has not accepted the current terms to the welcome page", async () => {
    const { load, s } = await world("ana", false);
    expect(await guardMember(s, load, "research")).toEqual({ kind: "redirect", to: "/welcome" });
  });
  it("sends a free member who types a paid address to the upgrade page", async () => {
    const { load, s } = await world("bo");
    expect(await guardMember(s, load, "research")).toEqual({ kind: "redirect", to: "/upgrade" });
    expect((await guardMember(s, load, "library")).kind).toBe("ok");
  });
  it("reports a service failure without redirecting", async () => {
    const failing = async () => { throw new ApiError(503, "unavailable", "", null); };
    expect(await guardMember("s", failing)).toEqual({ kind: "unavailable" });
  });
});
```

- [ ] **Step 2: See them fail**

Run: `npm test -- tests/member.test.ts`
Expected: FAIL, cannot resolve `@/lib/member`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 7 new tests pass, and `npm run build` lists `/member` as a dynamic route.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: workspace shell with a server guard and navigation from the member's sections"
```

---

### Task 3: The Account page

**Files:**
- Create: `lib/reasons.ts`, `app/member/account/page.tsx`, `app/member/components/DeleteAccount.tsx`, `app/api/account/delete/route.ts`, `tests/reasons.test.ts`, `tests/account.test.tsx`

**Interfaces:**
- Produces: `formatDate(iso: string | null): string | null` and `reasonText(reason: Reason): string`, with exactly these sentences (`<date>` is `formatDate(valid_until)`; the part in brackets is left out when there is no date):

| Reason | Sentence |
| --- | --- |
| `substack_subscription`, status `active` | "Included with your Substack subscription[, which renews on `<date>`]." |
| `substack_subscription`, status `grace` | "Included with your Substack subscription. A payment did not go through; access continues[ until `<date>`] while Substack retries." |
| `substack_status`, interval `month` | "You pay Substack on the monthly plan. Full access to the platform comes with the annual plan." |
| `substack_status`, interval `year` | "You pay Substack on the annual plan." |
| `substack_status`, no interval | "You have a Substack subscription that is not billed by card. It does not include the platform by itself." |
| `launch_grant`, status `active` | "Founding member access[ until `<date>`]." |
| `launch_grant` or `owner_grant`, any other status | "This access ended[ on `<date>`]." |
| `owner_grant`, status `active` | "Access granted by the publisher[ until `<date>`]." |
| `purchase` | "You bought this item." |
| anything else | "Access recorded." |

- The page (`requireMember("account")`): heading "Account"; "Signed in as `<email_hint>`"; a section "Your access" with the tier in words ("Full access" or "Free workspace") and one list item per reason from `access.reasons`; when the tier is `free`, a link "See how to upgrade" to `/upgrade`; a section "Terms" with the accepted versions and links to `/terms` and `/privacy`; a section "Delete your account" with the sentence "This removes your account and your records within 30 days. It does not cancel a Substack subscription." and the `DeleteAccount` component.
- `DeleteAccount`: a button "Delete my account" that first shows a confirmation ("Delete your account? You will be signed out now." with "Yes, delete it" and "Cancel"); on confirm it posts to `/api/account/delete` and, on 200, sends the browser to `/`; on failure it shows, with `role="alert"`, "That did not work. Please try again."
- `POST /api/account/delete`: the standard checks; calls `requestDeletion`; answers 200 `{ ok: true }` and clears the session cookie (`clearSessionCookieHeader`).

- [ ] **Step 1: Write the failing tests**

```ts
// tests/reasons.test.ts
// @vitest-environment node
import { describe, expect, it } from "vitest";
import type { Reason } from "@/lib/platform-api/types";
import { formatDate, reasonText } from "@/lib/reasons";

const r = (over: Partial<Reason>): Reason => ({ grant: "tier:paid", source: "substack_stripe", label: "substack_subscription",
  access_scope: "substack+platform", status: "active", valid_until: "2027-03-01T00:00:00Z", campaign: null, plan_interval: "year", ...over });

describe("reasonText", () => {
  it.each([
    [r({}), "Included with your Substack subscription, which renews on 1 March 2027."],
    [r({ valid_until: null }), "Included with your Substack subscription."],
    [r({ status: "grace" }), "Included with your Substack subscription. A payment did not go through; access continues until 1 March 2027 while Substack retries."],
    [r({ label: "substack_status", grant: "status:substack_paid", plan_interval: "month" }), "You pay Substack on the monthly plan. Full access to the platform comes with the annual plan."],
    [r({ label: "substack_status", grant: "status:substack_paid", plan_interval: null }), "You have a Substack subscription that is not billed by card. It does not include the platform by itself."],
    [r({ label: "launch_grant", source: "grant" }), "Founding member access until 1 March 2027."],
    [r({ label: "launch_grant", source: "grant", status: "expired" }), "This access ended on 1 March 2027."],
    [r({ label: "owner_grant", source: "grant", valid_until: null }), "Access granted by the publisher."],
    [r({ label: "purchase", source: "payhip", grant: "item:sample-map" }), "You bought this item."],
  ])("%#", (reason, text) => expect(reasonText(reason)).toBe(text));
  it("formats a date in UTC and gives null for none or nonsense", () =>
    expect([formatDate("2026-11-30T23:30:00Z"), formatDate(null), formatDate("soon")]).toEqual(["30 November 2026", null, null]));
});
```

```tsx
// tests/account.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DeleteAccount } from "@/app/member/components/DeleteAccount";

afterEach(() => vi.unstubAllGlobals());

describe("DeleteAccount", () => {
  it("asks before it deletes, and cancelling does nothing", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<DeleteAccount onDone={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete my account" })).toBeInTheDocument();
  });
  it("posts once on confirmation and reports when it is done", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const done = vi.fn();
    render(<DeleteAccount onDone={done} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, delete it" }));
    expect(fetchMock).toHaveBeenCalledWith("/api/account/delete", expect.objectContaining({ method: "POST" }));
    expect(done).toHaveBeenCalledOnce();
  });
  it("says so when it did not work", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 503 })));
    render(<DeleteAccount onDone={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, delete it" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That did not work. Please try again.");
  });
});
```

Add to a new file `tests/wave2-routes.test.ts`, written like `tests/terms-route.test.ts` (the same `vi.mock` of `getPlatformApi`, the same `req` helper): `POST /api/account/delete` answers 200, sets a `set-cookie` header that clears `session`, and `fake.me(...)` then fails; it answers 403 for another origin and 401 without a session. Three tests.

`DeleteAccount` takes `onDone` (default: `() => window.location.assign("/")`) so the test does not navigate.

- [ ] **Step 2: See them fail**

Run: `npm test -- tests/reasons.test.ts tests/account.test.tsx tests/wave2-routes.test.ts`
Expected: FAIL, cannot resolve `@/lib/reasons`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 16 new tests pass (10, 3 and 3).

- [ ] **Step 5: Commit; mark the pull request ready**

```bash
git add apps/web
git commit -m "web: Account page with access explained in plain words, and account deletion"
```

---

### Task 4: The upgrade page, "Check again" and the banner

**Files:**
- Create: `lib/upgrade.ts`, `app/upgrade/page.tsx`, `app/upgrade/CheckAgain.tsx`, `app/components/PromotionBanner.tsx`, `app/api/refresh-access/route.ts`, `app/api/tier/route.ts`, `tests/upgrade.test.tsx`
- Modify: `app/layout.tsx` or `app/components/Header.tsx` (show the banner on public pages), `tests/wave2-routes.test.ts`

**Interfaces:**
- Produces, in `lib/upgrade.ts`:

```ts
export type UpgradeView =
  | { kind: "paid" }
  | { kind: "change_plan"; url: string | null }
  | { kind: "subscribe"; url: string | null; offer: { badge: string; headline: string; body: string; ends: string | null } | null };
export function upgradeView(tier: "free" | "paid", options: UpgradeOptions): UpgradeView;
export async function pollUntilPaid(opts: { tier: () => Promise<"free" | "paid" | "signed_out">; sleep: (ms: number) => Promise<void>;
  everyMs?: number; forMs?: number }): Promise<"paid" | "timeout" | "signed_out">;      // defaults 5000 and 60000
```

- `upgradeView`: tier `paid` → `paid`. A route `substack_change_plan` → `change_plan` with its URL (`null` when not `available`). Otherwise the `substack` route's URL (`null` when missing or not `available`) and the promotion as `offer`, with `ends = formatDate(promotion.ends_at)`. The `platform_only` route is not shown while it is unavailable.
- `pollUntilPaid`: asks `tier()` at once, then after each `sleep(everyMs)`, until it answers `paid` or `signed_out`, or `forMs` has passed (then `timeout`). A `tier()` that throws counts as "not yet".
- `/upgrade` (server): `guardMember` without a section; `upgradeOptions`; a failure of that call shows "The upgrade options cannot be loaded right now. Please try again in a minute." Views:

| View | Shows |
| --- | --- |
| `paid` | Heading "You already have full access." and a link "Open your workspace" |
| `change_plan` | Heading "You are on the monthly plan." Text "Full access to the platform comes with the annual plan. You change your plan in your Substack account; nothing is charged here." A button-link "Change plan on Substack" (external, `rel="noreferrer"`); without a URL: "Open your Substack account and choose the annual plan." Then `CheckAgain` |
| `subscribe` | Heading "Get full access." The offer, when there is one: its badge, headline, body and "Offer ends `<ends>`." A button-link "Subscribe on Substack". Text "Subscriptions are sold and billed by Substack. When you have subscribed, come back and press Check again." Then `CheckAgain` |

- `CheckAgain` (client): a button "Check again". On press it posts to `/api/refresh-access`; 429 → `role="status"`: "Please wait a moment before checking again."; any other failure → "The check could not be started. Please try again in a minute."; otherwise it shows "Checking with Substack's payment records…" and runs `pollUntilPaid` against `GET /api/tier`; `paid` → reloads the page; `timeout` → "We did not find a paid subscription for this address yet. If you subscribed with another email address, sign in with that one, or use Tell us on the welcome page."; `signed_out` → sends the browser to `/join`. The button is disabled while a check runs.
- `POST /api/refresh-access` → the ticket's `check` as `{ check }` (status 200), 429 with `{ error: "rate_limited", retry_after }`, the standard 401 and 503. `GET /api/tier` → `{ tier }`, or 401.
- `PromotionBanner` (server component): calls `activePromotions()` inside `try`; nothing rendered on failure or when the list is empty; otherwise one line with the badge, the headline and a link "See the offer" to `/upgrade`. Shown in the public header, not inside `/member`. It must not make a public page fail: wrap the call so that any error renders nothing.

- [ ] **Step 1: Write the failing tests**

```tsx
// tests/upgrade.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CheckAgain } from "@/app/upgrade/CheckAgain";
import type { UpgradeOptions } from "@/lib/platform-api/types";
import { pollUntilPaid, upgradeView } from "@/lib/upgrade";

const promotion = { id: "p", channel: "substack_offer", plan_interval: "year" as const, starts_at: "2026-11-26T00:00:00Z", ends_at: "2026-11-30T23:00:00Z",
  url: "https://example.org/offer", display: { badge: "Offer", headline: "A headline", body: "A body" } };
const free = (over: Partial<UpgradeOptions> = {}): UpgradeOptions => ({
  routes: [{ kind: "substack", available: true, url: "https://example.org/subscribe" }, { kind: "platform_only", available: false, url: null }], promotion: null, ...over });

describe("upgradeView", () => {
  it("shows a paid member nothing to buy", () => expect(upgradeView("paid", { routes: [], promotion: null })).toEqual({ kind: "paid" }));
  it("shows a monthly payer how to change plan and no offer", () =>
    expect(upgradeView("free", { routes: [{ kind: "substack_change_plan", available: true, url: "https://example.org/subscribe" }], promotion: null }))
      .toEqual({ kind: "change_plan", url: "https://example.org/subscribe" }));
  it("shows a free member the subscribe route, with the offer and its end when there is one", () => {
    expect(upgradeView("free", free())).toEqual({ kind: "subscribe", url: "https://example.org/subscribe", offer: null });
    const withOffer = upgradeView("free", free({ routes: [{ kind: "substack", available: true, url: promotion.url }], promotion }));
    expect(withOffer).toEqual({ kind: "subscribe", url: "https://example.org/offer", offer: { badge: "Offer", headline: "A headline", body: "A body", ends: "30 November 2026" } });
  });
  it("gives no link when the route is not available", () =>
    expect(upgradeView("free", { routes: [{ kind: "substack", available: false, url: null }], promotion: null })).toEqual({ kind: "subscribe", url: null, offer: null }));
});

describe("pollUntilPaid", () => {
  const clock = () => { const slept: number[] = []; return { slept, sleep: async (ms: number) => { slept.push(ms); } }; };
  it("stops as soon as the member is paid", async () => {
    const { slept, sleep } = clock();
    const answers = ["free", "free", "paid"] as const;
    let i = 0;
    expect(await pollUntilPaid({ tier: async () => answers[i++], sleep })).toBe("paid");
    expect(slept).toEqual([5000, 5000]);
  });
  it("gives up after a minute", async () => {
    const { slept, sleep } = clock();
    expect(await pollUntilPaid({ tier: async () => "free", sleep })).toBe("timeout");
    expect(slept.reduce((a, b) => a + b, 0)).toBe(60000);
  });
  it("treats a failed request as not yet, and stops when signed out", async () => {
    const { sleep } = clock();
    let n = 0;
    expect(await pollUntilPaid({ tier: async () => { if (n++ === 0) throw new Error("network"); return "signed_out"; }, sleep })).toBe("signed_out");
  });
});

describe("CheckAgain", () => {
  afterEach(() => vi.unstubAllGlobals());
  const respond = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });
  it("starts a check, then reports that nothing was found after the time is up", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === "/api/refresh-access" ? respond(200, { check: "started" }) : respond(200, { tier: "free" }))));
    render(<CheckAgain sleep={async () => {}} onPaid={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByText(/We did not find a paid subscription for this address yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeEnabled();
  });
  it("reloads when the member has become paid", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => (url === "/api/refresh-access" ? respond(200, { check: "started" }) : respond(200, { tier: "paid" }))));
    const onPaid = vi.fn();
    render(<CheckAgain sleep={async () => {}} onPaid={onPaid} />);
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    await vi.waitFor(() => expect(onPaid).toHaveBeenCalledOnce());
  });
  it("asks the member to wait when the limit is reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => respond(429, { error: "rate_limited", retry_after: 30 })));
    render(<CheckAgain sleep={async () => {}} onPaid={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Check again" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Please wait a moment before checking again.");
  });
});
```

Add to `tests/wave2-routes.test.ts`: `POST /api/refresh-access` answers `{ check: "started" }` for `bo`, 403 for another origin, 401 without a session, and 429 with `retry_after` when the fake is told `failNext("rate_limited")`; `GET /api/tier` answers `{ tier: "free" }` for `bo` and 401 without a session. Six tests.

`CheckAgain` takes `sleep` (default: a timer) and `onPaid` (default: `() => window.location.reload()`).

- [ ] **Step 2: See them fail**

Run: `npm test -- tests/upgrade.test.tsx`
Expected: FAIL, cannot resolve `@/lib/upgrade`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 16 new tests pass (4, 3, 3 and 6).

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: upgrade page per kind of member, Check again with a one-minute limit, public offer banner"
```

---

### Task 5: The library

**Files:**
- Create: `lib/library.ts`, `app/member/library/page.tsx`, `app/member/library/[sku]/page.tsx`, `app/member/research/page.tsx`, `app/member/guides/page.tsx`, `app/member/components/ItemList.tsx`, `DownloadButton.tsx`, `app/api/library/[sku]/download/route.ts`, `tests/library.test.tsx`
- Modify: `tests/wave2-routes.test.ts`

**Interfaces:**
- Produces, in `lib/library.ts`:

```ts
export const KIND_LABEL: Record<ItemKind, string>;   // "Meta-review", "Evidence map", "Clinician one-pager", "Guide", "Worksheet"
export type CardAction = { kind: "download" } | { kind: "buy"; url: string } | { kind: "upgrade" } | { kind: "none" };
export function cardAction(item: ItemCard): CardAction;
export function viewOf(items: ItemCard[], view: "all" | "research" | "guides"): ItemCard[];
export function refusalText(status: number, reason: string | null): { text: string; link: { href: string; label: string } | null };
```

- `cardAction`: `can_open` → `download`; else a `buy_url` → `buy`; else access `paid` → `upgrade`; else `none`.
- `refusalText`: 403 `paid_required` → "This item is part of full access." with the link "See how to upgrade" to `/upgrade`; 403 `purchase_required` → "This item is sold separately." and no link; 429 → "You have downloaded many files in the last hour. Please try again later."; 404 → "This item is no longer available."; anything else → "The download could not be prepared. Please try again in a minute."
- Pages: `/member/library` (`requireMember("library")`, heading "Library", every card); `/member/research` and `/member/guides` (`requireMember("research")` / `("guides")`, the filtered view; an empty view says "Nothing here yet."); `/member/library/[sku]` (title, kind, version, pages when not 0, the description, the citation when there is one, and the card's action; an unknown sku → Next's `notFound()`). A failure to load the catalogue shows "The library cannot be loaded right now. Please try again in a minute."
- `ItemList` shows per card: title (a link to its page), `KIND_LABEL`, the abstract, and its action: `DownloadButton`, or a link "Buy" (external), or a link "Upgrade to open" to `/upgrade`.
- `DownloadButton` (client): a button "Download". On press it posts to `/api/library/<sku>/download`; on 200 it sends the browser to the returned URL (`onUrl`, default `window.location.assign`); otherwise it shows `refusalText` with `role="alert"`, and its link when there is one.
- `POST /api/library/[sku]/download`: the standard checks; a `sku` that does not match `^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$` → 404 without calling the service; on success 200 `{ url }`; an `ApiError` 403 → 403 `{ error: "forbidden", reason }`; 404 → 404; 429 → 429; otherwise 503.

- [ ] **Step 1: Write the failing tests**

```tsx
// tests/library.test.tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DownloadButton } from "@/app/member/components/DownloadButton";
import { ItemList } from "@/app/member/components/ItemList";
import { cardAction, refusalText, viewOf } from "@/lib/library";
import type { ItemCard } from "@/lib/platform-api/types";

const card = (over: Partial<ItemCard>): ItemCard => ({ sku: "sample-map", title: "Sample map", kind: "evidence_map", abstract: "An invented item.",
  version: "1.0", pages: 4, access: "paid", can_open: false, buy_url: null, ...over });

describe("cardAction", () => {
  it.each([
    [card({ can_open: true }), { kind: "download" }],
    [card({ buy_url: "https://example.org/buy" }), { kind: "buy", url: "https://example.org/buy" }],
    [card({}), { kind: "upgrade" }],
    [card({ access: "purchase_only" }), { kind: "none" }],
  ])("%#", (item, action) => expect(cardAction(item)).toEqual(action));
});

describe("viewOf", () => {
  const items = [card({ sku: "a" }), card({ sku: "b", kind: "guide" }), card({ sku: "c", kind: "worksheet" }), card({ sku: "d", kind: "meta_review" })];
  it("splits the catalogue into research and guides", () => {
    expect(viewOf(items, "research").map((i) => i.sku)).toEqual(["a", "d"]);
    expect(viewOf(items, "guides").map((i) => i.sku)).toEqual(["b", "c"]);
    expect(viewOf(items, "all")).toHaveLength(4);
  });
});

describe("refusalText", () => {
  it.each([
    [403, "paid_required", "This item is part of full access.", "/upgrade"],
    [403, "purchase_required", "This item is sold separately.", null],
    [429, null, "You have downloaded many files in the last hour. Please try again later.", null],
    [404, null, "This item is no longer available.", null],
    [503, null, "The download could not be prepared. Please try again in a minute.", null],
  ])("%#", (status, reason, text, href) => {
    const out = refusalText(status, reason);
    expect([out.text, out.link?.href ?? null]).toEqual([text, href]);
  });
});

describe("ItemList and DownloadButton", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("offers download, buy or upgrade per card", () => {
    render(<ItemList items={[card({ sku: "a", title: "A", can_open: true }), card({ sku: "b", title: "B", buy_url: "https://example.org/buy" }), card({ sku: "c", title: "C" })]} />);
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Buy" })).toHaveAttribute("href", "https://example.org/buy");
    expect(screen.getByRole("link", { name: "Upgrade to open" })).toHaveAttribute("href", "/upgrade");
    expect(screen.getByRole("link", { name: "A" })).toHaveAttribute("href", "/member/library/a");
  });
  it("goes to the signed link", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ url: "https://files.invalid/sample-map" }), { status: 200 })));
    const onUrl = vi.fn();
    render(<DownloadButton sku="sample-map" onUrl={onUrl} />);
    await userEvent.click(screen.getByRole("button", { name: "Download" }));
    await vi.waitFor(() => expect(onUrl).toHaveBeenCalledWith("https://files.invalid/sample-map"));
  });
  it("explains a refusal and shows the upgrade route", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "forbidden", reason: "paid_required" }), { status: 403 })));
    render(<DownloadButton sku="sample-map" onUrl={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Download" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This item is part of full access.");
    expect(screen.getByRole("link", { name: "See how to upgrade" })).toHaveAttribute("href", "/upgrade");
  });
});
```

Add to `tests/wave2-routes.test.ts`: the download route answers 200 with a URL for `ana`; 403 with `reason: "paid_required"` for `bo`; 404 for `Sample..Map` without the fake being asked (spy on `fake.download`); 403 for another origin; 401 without a session. Five tests. The route handler receives its `sku` as Next 16 passes route parameters (`{ params }: { params: Promise<{ sku: string }> }`).

- [ ] **Step 2: See them fail**

Run: `npm test -- tests/library.test.tsx`
Expected: FAIL, cannot resolve `@/lib/library`.

- [ ] **Step 3: Implement**

- [ ] **Step 4: See them pass**

Run the check command. Expected: 18 new tests pass (4, 1, 5, 3 and 5).

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "web: library pages, research and guides views, download with plain refusals"
```

---

### Task 6: The legal pages, the terms step and the Google button

**Files:**
- Create: `lib/legal.ts`, `tests/legal.test.ts`
- Modify: `app/terms/page.tsx`, `app/privacy/page.tsx`, `app/welcome/TermsStep.tsx`, `app/join/JoinScreen.tsx` and the page that renders it, `lib/identity/config.ts`, `next.config.ts`, `package.json`, `tests/welcome.test.tsx`, `tests/join-screen.test.tsx`

**Interfaces:**
- Produces: `readLegal(name: "terms" | "privacy", dir?: string): { title: string; version: string; effectiveFrom: string; html: string }`. It reads `content/legal/<name>.md` (from `process.cwd()` unless `dir` is given), takes `title`, `version` and `effective_from` from the front matter between the first two `---` lines (a missing key throws an `Error` that names it), and renders the rest with `marked` (GitHub-style tables on).
- `/terms` and `/privacy`: the rendered text inside `<article className="legal">`, with a line above it: "Version `<version>`, in force from `<formatDate(effectiveFrom)>`." Both pages are static (`dynamic = "force-static"`) and may be indexed.
- `next.config.ts`: `outputFileTracingIncludes` for `/terms` and `/privacy` with `./content/legal/*`, so the files are inside the standalone output. **Read the Next.js documentation for this option in the installed version before writing it**, and check after `npm run build` that `.next/standalone/content/legal/terms.md` exists (add that check to the `build-test` job's script in a `cross-lane` pull request to the Infra lane if the workflow does not already run from `apps/web`).
- `TermsStep`: above the button, the sentences "Please read the [terms of use](/terms) and the [privacy notice](/privacy)." and "By continuing you confirm that you are 18 or older and that you agree to both." The button reads "I agree and continue". The versions being accepted are shown: "Terms `<terms_version>`, privacy notice `<privacy_version>`."
- `identityConfig` gains `googleEnabled: boolean` on the `firebase` and `fake` kinds: true for `fake`; for `firebase`, true only when `IDENTITY_GOOGLE_ENABLED === "1"`. `JoinScreen` takes `googleEnabled` and renders neither the Google button nor the sentence that mentions it when it is false; the spam-folder hint then reads "If it is not there after a minute, look in the spam folder."

- [ ] **Step 1: Write the failing tests**

```ts
// tests/legal.test.ts
// @vitest-environment node
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { identityConfig } from "@/lib/identity/config";
import { readLegal } from "@/lib/legal";

const dirWith = (name: string, text: string) => { const d = mkdtempSync(join(tmpdir(), "legal-")); writeFileSync(join(d, `${name}.md`), text); return d; };

describe("readLegal", () => {
  it("reads the two approved texts with their versions", () => {
    for (const name of ["terms", "privacy"] as const) {
      const doc = readLegal(name);
      expect(doc.version).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(doc.effectiveFrom).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(doc.html).toContain("<h1");
      expect(doc.html).not.toContain("effective_from");
    }
    expect(readLegal("privacy").html).toContain("<table>");
  });
  it("names a missing front-matter key", () => {
    const dir = dirWith("terms", "---\ntitle: T\nversion: 2026-01-01\n---\n\n# T\n");
    expect(() => readLegal("terms", dir)).toThrow(/effective_from/);
  });
  it("refuses a file without front matter", () =>
    expect(() => readLegal("terms", dirWith("terms", "# T\n"))).toThrow(/front matter/));
});

describe("identityConfig, Google button", () => {
  const base = { IDENTITY_API_KEY: "k", IDENTITY_AUTH_DOMAIN: "d", SITE_ENV: "dev" };
  it("is off unless the setting says 1", () => {
    expect(identityConfig(base)).toMatchObject({ kind: "firebase", googleEnabled: false });
    expect(identityConfig({ ...base, IDENTITY_GOOGLE_ENABLED: "1" })).toMatchObject({ kind: "firebase", googleEnabled: true });
    expect(identityConfig({ PLATFORM_API_FAKE: "1", SITE_ENV: "dev" })).toMatchObject({ kind: "fake", googleEnabled: true });
  });
});
```

In `tests/welcome.test.tsx`, change the terms-step test to the new button name and add assertions that the two links point to `/terms` and `/privacy` and that the sentence about being 18 or older is present. In `tests/join-screen.test.tsx`, add two tests: with `googleEnabled={false}` there is no button named "Continue with Google" and no text containing "Continue with Google"; with `true` the button is there. Existing tests that render `JoinScreen` pass `googleEnabled` explicitly.

- [ ] **Step 2: See them fail**

Run: `npm test -- tests/legal.test.ts`
Expected: FAIL, cannot resolve `@/lib/legal`.

- [ ] **Step 3: Implement**

Install `marked` at an exact version (`npm install --save-exact marked`). Add the class `legal` to `globals.css` with readable line length and table borders.

- [ ] **Step 4: See them pass**

Run the check command. Expected: 4 new tests pass in `legal.test.ts`, 2 new in `join-screen.test.tsx`; `npm run build` lists `/terms` and `/privacy` as static; `.next/standalone/content/legal/terms.md` exists.

- [ ] **Step 5: Commit; mark the second pull request ready**

```bash
git add apps/web
git commit -m "web: terms and privacy pages from the approved texts; terms step states age and versions; Google button behind a setting"
```

---

## Exit test for this plan

1. The check command passes in CI.
2. With `PLATFORM_API_FAKE=1 npm run dev`, signed in as each fixture person: `ana` sees five navigation entries and can download `sample-map`; `bo` sees three, is sent from `/member/research` to `/upgrade`, and sees "Subscribe on Substack"; `hal` sees "You are on the monthly plan." on `/upgrade`; deleting the account signs the person out.
3. A search of the lane's diff finds no percentage, price or date of an offer, and no address outside `example.org`.
4. The hand-over lists for the Infra lane the new setting `IDENTITY_GOOGLE_ENABLED`, and for the Quality lane the pages to include in the accessibility pass: `/member`, `/member/account`, `/member/library`, `/member/library/[sku]`, `/upgrade`, `/terms`, `/privacy`.
