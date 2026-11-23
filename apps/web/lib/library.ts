import { redirect } from "next/navigation";
import { ApiError } from "@/lib/platform-api/errors";
import type { ItemCard, ItemDetail, ItemKind } from "@/lib/platform-api/types";

export const KIND_LABEL: Record<ItemKind, string> = {
  meta_review: "Meta-review",
  evidence_map: "Evidence map",
  clinician_one_pager: "Clinician one-pager",
  guide: "Guide",
  worksheet: "Worksheet",
};

export const SKU_PATTERN = /^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$/;

export const CANNOT_LOAD = "The library cannot be loaded right now. Please try again in a minute.";

export type CardAction = { kind: "download" } | { kind: "buy"; url: string } | { kind: "upgrade" };

export function cardActions(item: ItemCard): CardAction[] {
  if (item.can_open) return [{ kind: "download" }];
  const actions: CardAction[] = [];
  if (item.buy_url) actions.push({ kind: "buy", url: item.buy_url });
  // Full access does not open a purchase_only item, so no upgrade is offered for one.
  if (item.access === "paid") actions.push({ kind: "upgrade" });
  return actions;
}

export type LibraryCounts = { total: number; open: number };

export function libraryCounts(items: ItemCard[]): LibraryCounts {
  return { total: items.length, open: items.filter((i) => i.can_open).length };
}

// The overview never fails because of the library: any failure means no count.
export async function overviewCounts(
  sessionOf: () => Promise<string>,
  list: (session: string) => Promise<ItemCard[]>,
): Promise<LibraryCounts | null> {
  const session = await sessionOf(); // may redirect (it throws), so it stays outside the try
  try {
    return libraryCounts(await list(session));
  } catch {
    return null;
  }
}

// Words for a well-formed sku the service does not know: the library is off when the list is not found too.
export async function missingItemText(
  sessionOf: () => Promise<string>,
  list: (session: string) => Promise<ItemCard[]>,
): Promise<string> {
  const session = await sessionOf(); // may redirect (it throws), so it stays outside the try
  try {
    await list(session);
  } catch (error) {
    if (error instanceof ApiError && error.code === "not_found") return "The library opens soon.";
  }
  return "This item is no longer available.";
}

const RESEARCH: ItemKind[] = ["meta_review", "evidence_map", "clinician_one_pager"];

export function viewOf(items: ItemCard[], view: "all" | "research" | "guides"): ItemCard[] {
  if (view === "all") return items;
  return items.filter((i) => RESEARCH.includes(i.kind) === (view === "research"));
}

export function refusalText(status: number, reason: string | null): { text: string; link: { href: string; label: string } | null } {
  if (status === 403 && reason === "paid_required")
    return { text: "This item is part of full access.", link: { href: "/upgrade", label: "See how to upgrade" } };
  if (status === 403 && reason === "purchase_required") return { text: "This item is sold separately.", link: null };
  if (status === 429)
    return { text: "You have downloaded many files in the last hour. Please try again later.", link: null };
  if (status === 404) return { text: "This item is no longer available.", link: null };
  return { text: "The download could not be prepared. Please try again in a minute.", link: null };
}

export type ViewResult = { kind: "items"; items: ItemCard[] } | { kind: "message"; text: string };

// Where an answer from the service sends the browser; null when it is not one of those.
function redirectFor(error: unknown): string | null {
  if (error instanceof ApiError && error.code === "unauthenticated") return "/join";
  if (error instanceof ApiError && error.code === "terms_required") return "/welcome";
  return null;
}

// The guard runs first, then the session; both may redirect (they throw), so neither sits inside the try.
// redirect() is also called outside the try.
export async function loadView(
  view: "all" | "research" | "guides",
  guard: () => Promise<unknown>,
  sessionOf: () => Promise<string>,
  list: (session: string) => Promise<ItemCard[]>,
): Promise<ViewResult> {
  await guard();
  const session = await sessionOf();
  let items: ItemCard[] | null = null;
  let failure: unknown = null;
  try {
    items = await list(session);
  } catch (error) {
    failure = error;
  }
  if (items === null) {
    const to = redirectFor(failure);
    if (to) redirect(to);
    if (failure instanceof ApiError && failure.code === "not_found") return { kind: "message", text: "The library opens soon." };
    return { kind: "message", text: CANNOT_LOAD };
  }
  const shown = viewOf(items, view);
  return shown.length === 0 ? { kind: "message", text: "Nothing here yet." } : { kind: "items", items: shown };
}

export type ItemResult = { kind: "item"; detail: ItemDetail } | { kind: "not_found" } | { kind: "message"; text: string };

export async function loadItem(
  sku: string,
  guard: () => Promise<unknown>,
  sessionOf: () => Promise<string>,
  get: (session: string) => Promise<ItemDetail>,
): Promise<ItemResult> {
  if (!SKU_PATTERN.test(sku)) return { kind: "not_found" };
  await guard();
  const session = await sessionOf();
  let detail: ItemDetail | null = null;
  let failure: unknown = null;
  try {
    detail = await get(session);
  } catch (error) {
    failure = error;
  }
  if (detail) return { kind: "item", detail };
  const to = redirectFor(failure);
  if (to) redirect(to);
  if (failure instanceof ApiError && failure.code === "not_found") return { kind: "not_found" };
  return { kind: "message", text: CANNOT_LOAD };
}
