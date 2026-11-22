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
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete my account" })).toHaveFocus();
  });
  it("posts once on confirmation and reports when it is done", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const done = vi.fn();
    render(<DeleteAccount onDone={done} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, delete it" }));
    expect(fetchMock).toHaveBeenCalledWith("/api/account/delete", expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
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
