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
  if (accept) await api.acceptTerms(session.cookie, "terms-v1", "privacy-v1");
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
    render(<TermsStep accept={accept} reload={() => {}} />);
    const button = screen.getByRole("button", { name: "Continue" });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(button);
    expect(accept).toHaveBeenCalledOnce();
  });
  it("reloads after accepting", async () => {
    const reload = vi.fn();
    render(<TermsStep accept={vi.fn().mockResolvedValue(undefined)} reload={reload} />);
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(reload).toHaveBeenCalledOnce();
  });
  it("says so and keeps the form when accepting fails", async () => {
    const reload = vi.fn();
    render(<TermsStep accept={vi.fn().mockRejectedValue(new Error("x"))} reload={reload} />);
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Something went wrong. Try again.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
    expect(reload).not.toHaveBeenCalled();
  });
  it("links the terms and the privacy notice", () => {
    render(<TermsStep accept={vi.fn()} reload={() => {}} />);
    expect(screen.getByRole("link", { name: "terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "privacy notice" })).toHaveAttribute("href", "/privacy");
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
  it("asks to accept the terms first on a 409", async () => {
    const send = vi.fn().mockRejectedValue(Object.assign(new Error("x"), { status: 409 }));
    render(<NotRecognised send={send} />);
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Accept the terms first.")).toBeInTheDocument();
  });
  it("shows a general message on another failure", async () => {
    render(<NotRecognised send={vi.fn().mockRejectedValue(new Error("x"))} />);
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Something went wrong. Try again.")).toBeInTheDocument();
  });
  it("limits the note to 500 characters", () => {
    render(<NotRecognised send={vi.fn()} />);
    expect(screen.getByLabelText("Tell us what happened")).toHaveAttribute("maxlength", "500");
  });
  it("signs out and goes to /join, even when the sign-out fails", async () => {
    const go = vi.fn();
    const signOut = vi.fn().mockRejectedValue(new Error("x"));
    render(<NotRecognised send={vi.fn()} signOut={signOut} go={go} />);
    await userEvent.click(screen.getByRole("button", { name: "Sign in with another email" }));
    expect(signOut).toHaveBeenCalledOnce();
    expect(go).toHaveBeenCalledWith("/join");
  });
});
