import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DownloadButton } from "@/app/member/components/DownloadButton";
import { ItemList } from "@/app/member/components/ItemList";
import { cardAction, loadItem, loadView, refusalText, viewOf } from "@/lib/library";
import { ApiError } from "@/lib/platform-api/errors";
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

const sess = async () => "s1";
const redirectTo = (to: string) => expect.objectContaining({ digest: expect.stringContaining(to) });

describe("loadView", () => {
  const redirected = new Error("NEXT_REDIRECT");
  it("sends a free member away before any library call", async () => {
    const list = vi.fn(async () => [card({})]);
    await expect(loadView("research", async () => { throw redirected; }, sess, list)).rejects.toBe(redirected);
    expect(list).not.toHaveBeenCalled();
  });
  it("calls the guard, then the session, then lists with that session and filters", async () => {
    const order: string[] = [];
    const out = await loadView("guides", async () => { order.push("guard"); }, async () => { order.push("session"); return "s1"; },
      async (s) => { order.push(`list:${s}`); return [card({ sku: "a" }), card({ sku: "b", kind: "guide" })]; });
    expect(order).toEqual(["guard", "session", "list:s1"]);
    expect(out).toEqual({ kind: "items", items: [expect.objectContaining({ sku: "b" })] });
  });
  it("says so when the view is empty", async () => {
    expect(await loadView("research", async () => {}, sess, async () => [])).toEqual({ kind: "message", text: "Nothing here yet." });
  });
  it("says the library opens soon when the service has none", async () => {
    const out = await loadView("all", async () => {}, sess, async () => { throw new ApiError(404, "not_found", "x"); });
    expect(out).toEqual({ kind: "message", text: "The library opens soon." });
  });
  it.each([[429, "rate_limited"], [503, "unavailable"]] as const)("keeps the page working on %i", async (status, code) => {
    const out = await loadView("all", async () => {}, sess, async () => { throw new ApiError(status, code, "x"); });
    expect(out).toEqual({ kind: "message", text: "The library cannot be loaded right now. Please try again in a minute." });
  });
  it("sends an unauthenticated answer to /join and terms_required to /welcome", async () => {
    await expect(loadView("all", async () => {}, sess, async () => { throw new ApiError(401, "unauthenticated", "x"); })).rejects.toEqual(redirectTo("/join"));
    await expect(loadView("all", async () => {}, sess, async () => { throw new ApiError(409, "terms_required", "x"); })).rejects.toEqual(redirectTo("/welcome"));
  });
  it("does not swallow a redirect thrown by the session helper", async () => {
    const list = vi.fn(async () => [card({})]);
    await expect(loadView("all", async () => {}, async () => { throw redirected; }, list)).rejects.toBe(redirected);
    expect(list).not.toHaveBeenCalled();
  });
});

describe("loadItem", () => {
  it("answers not found for a malformed sku without guard or service", async () => {
    const guard = vi.fn(async () => {});
    const get = vi.fn();
    expect(await loadItem("Sample..Map", guard, sess, get)).toEqual({ kind: "not_found" });
    expect(get).not.toHaveBeenCalled();
  });
  it("answers not found for an unknown sku and a message on failure", async () => {
    expect(await loadItem("nope-nope", async () => {}, sess, async () => { throw new ApiError(404, "not_found", "x"); })).toEqual({ kind: "not_found" });
    expect(await loadItem("nope-nope", async () => {}, sess, async () => { throw new ApiError(503, "unavailable", "x"); })).toEqual({
      kind: "message", text: "The library cannot be loaded right now. Please try again in a minute." });
  });
  it("passes the session on, redirects on 401 and 409, and does not swallow a session redirect", async () => {
    const get = vi.fn(async (_s: string) => { throw new ApiError(401, "unauthenticated", "x"); });
    await expect(loadItem("nope-nope", async () => {}, sess, get)).rejects.toEqual(redirectTo("/join"));
    expect(get).toHaveBeenCalledWith("s1");
    await expect(loadItem("nope-nope", async () => {}, sess, async () => { throw new ApiError(409, "terms_required", "x"); })).rejects.toEqual(redirectTo("/welcome"));
    const redirected = new Error("NEXT_REDIRECT");
    await expect(loadItem("nope-nope", async () => {}, async () => { throw redirected; }, vi.fn())).rejects.toBe(redirected);
  });
});

describe("ItemList and DownloadButton", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("offers download, buy or upgrade per card", () => {
    render(<ItemList items={[card({ sku: "a", title: "A", can_open: true }), card({ sku: "b", title: "B", buy_url: "https://example.org/buy" }), card({ sku: "c", title: "C" })]} />);
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Buy" })).toHaveAttribute("href", "https://example.org/buy");
    expect(screen.getByRole("link", { name: "Buy" })).toHaveAttribute("rel", "noreferrer");
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
  it("sends the browser to welcome when the terms are not accepted", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "terms_required" }), { status: 409 })));
    const navigate = vi.fn();
    render(<DownloadButton sku="sample-map" onUrl={() => {}} navigate={navigate} />);
    await userEvent.click(screen.getByRole("button", { name: "Download" }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("/welcome"));
  });
  it("sends the browser to sign in without a session", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: "unauthenticated" }), { status: 401 })));
    const navigate = vi.fn();
    render(<DownloadButton sku="sample-map" onUrl={() => {}} navigate={navigate} />);
    await userEvent.click(screen.getByRole("button", { name: "Download" }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("/join"));
  });
});
