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

export type CardAction = { kind: "download" } | { kind: "buy"; url: string } | { kind: "upgrade" } | { kind: "none" };

export function cardAction(item: ItemCard): CardAction {
  if (item.can_open) return { kind: "download" };
  if (item.buy_url) return { kind: "buy", url: item.buy_url };
  if (item.access === "paid") return { kind: "upgrade" };
  return { kind: "none" };
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

// The guard runs first and may redirect (it throws); only then is the catalogue asked for.
export async function loadView(
  view: "all" | "research" | "guides",
  guard: () => Promise<unknown>,
  list: () => Promise<ItemCard[]>,
): Promise<ViewResult> {
  await guard();
  let items: ItemCard[];
  try {
    items = await list();
  } catch (error) {
    if (error instanceof ApiError && error.code === "not_found") return { kind: "message", text: "The library opens soon." };
    return { kind: "message", text: CANNOT_LOAD };
  }
  const shown = viewOf(items, view);
  return shown.length === 0 ? { kind: "message", text: "Nothing here yet." } : { kind: "items", items: shown };
}

export type ItemResult = { kind: "item"; detail: ItemDetail } | { kind: "not_found" } | { kind: "message"; text: string };

export async function loadItem(
  sku: string,
  guard: () => Promise<unknown>,
  get: () => Promise<ItemDetail>,
): Promise<ItemResult> {
  if (!SKU_PATTERN.test(sku)) return { kind: "not_found" };
  await guard();
  try {
    return { kind: "item", detail: await get() };
  } catch (error) {
    if (error instanceof ApiError && error.code === "not_found") return { kind: "not_found" };
    return { kind: "message", text: CANNOT_LOAD };
  }
}
