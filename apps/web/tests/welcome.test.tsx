import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TermsStep } from "@/app/welcome/TermsStep";
import { NotRecognised } from "@/app/welcome/NotRecognised";
import { FakePlatformApi } from "@/lib/platform-api/fake";
import { ApiError } from "@/lib/platform-api/errors";
import { termsCurrent, welcomeState, welcomeView } from "@/lib/welcome";
import { WelcomeBody } from "@/app/welcome/WelcomeBody";
import { SignOutButton } from "@/app/welcome/SignOutButton";

const meOf = async (name: string, accept = true) => {
  const api = new FakePlatformApi();
  const { session } = await api.resolveSession(`fake-token:${name}`, null);
  if (accept) await api.acceptTerms(session.cookie, "terms-v1", "privacy-v1");
  return api.me(session.cookie);
};

describe("termsCurrent", () => {
  it("is true only when accepted and both versions match the required ones", async () => {
    const { member } = await meOf("ana");
    expect(termsCurrent(member)).toBe(true);
    expect(termsCurrent({ ...member, terms: { ...member.terms, terms_version: "old" } })).toBe(false);
    expect(termsCurrent({ ...member, terms: { ...member.terms, privacy_version: "old" } })).toBe(false);
    expect(termsCurrent({ ...member, terms: { ...member.terms, privacy_version: null } })).toBe(false);
    expect(termsCurrent({ ...member, terms: { ...member.terms, accepted: false } })).toBe(false);
  });
});

describe("welcomeView", () => {
  it("asks again when the required terms version has moved on", async () => {
    const me = await meOf("ana");
    const stale = { ...me, member: { ...me.member, terms: { ...me.member.terms, terms_version: "old" } } };
    expect(welcomeView(stale, null)).toEqual({ kind: "terms", versions: { terms: "terms-v1", privacy: "privacy-v1" } });
  });
  it("asks for the terms first", async () => expect(welcomeView(await meOf("ana", false), null)).toEqual({ kind: "terms", versions: { terms: "terms-v1", privacy: "privacy-v1" } }));
  it("shows ana as paid, included while paying, with a guarantee date", async () => {
    const view = welcomeView(await meOf("ana"), null);
    expect(view).toMatchObject({ kind: "paid", includedWhilePaying: true });
    expect(view.kind === "paid" && view.grantUntil).toBeTruthy();
  });
  it("shows fay as paid through the grant alone", async () =>
    expect(welcomeView(await meOf("fay"), null)).toMatchObject({ kind: "paid", includedWhilePaying: false }));
  it("shows hal as a paying reader whose plan does not include the platform", async () =>
    expect(welcomeView(await meOf("hal"), null)).toEqual({ kind: "other_plan", planInterval: "month" }));
  it("shows di as free, with no plan interval to show", async () =>
    expect(welcomeView(await meOf("di"), null)).toEqual({ kind: "free", checking: false }));
  it("shows an annual status reason as the annual plan", async () => {
    const me = await meOf("hal");
    me.access.reasons = me.access.reasons.map((r) => ({ ...r, plan_interval: "year" as const }));
    expect(welcomeView(me, null)).toEqual({ kind: "other_plan", planInterval: "year" });
  });
  it("shows a status reason that is neither active nor in grace as free", async () => {
    const me = await meOf("hal");
    me.access.reasons = me.access.reasons.map((r) => ({ ...r, status: "ended" }));
    expect(welcomeView(me, null)).toEqual({ kind: "free", checking: false });
  });
  it("shows a status reason in grace as the plan", async () => {
    const me = await meOf("hal");
    me.access.reasons = me.access.reasons.map((r) => ({ ...r, status: "grace" }));
    expect(welcomeView(me, null)).toEqual({ kind: "other_plan", planInterval: "month" });
  });
  it("ignores a launch grant whose end date does not parse", async () => {
    const me = await meOf("ana");
    me.access.reasons = me.access.reasons.map((r) => (r.label === "launch_grant" ? { ...r, valid_until: "not-a-date" } : r));
    expect(welcomeView(me, null)).toMatchObject({ kind: "paid", grantUntil: null });
  });
  it("shows bo as free, checking only when a check was started", async () => {
    expect(welcomeView(await meOf("bo"), null)).toEqual({ kind: "free", checking: false });
    expect(welcomeView(await meOf("bo"), "started")).toEqual({ kind: "free", checking: true });
    expect(welcomeView(await meOf("bo"), "anything-else")).toEqual({ kind: "free", checking: false });
  });
});

const versions = { terms: "terms-v1", privacy: "privacy-v1" };
describe("TermsStep", () => {
  it("has no checkbox and accepts on the button", async () => {
    const accept = vi.fn().mockResolvedValue(undefined);
    render(<TermsStep accept={accept} reload={() => {}} versions={versions} />);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "I agree and continue" }));
    expect(accept).toHaveBeenCalledOnce();
    expect(accept).toHaveBeenCalledWith({ terms_version: "terms-v1", privacy_version: "privacy-v1" });
  });
  it("posts the versions it shows as JSON", async () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<TermsStep reload={() => {}} versions={versions} />);
    await userEvent.click(screen.getByRole("button", { name: "I agree and continue" }));
    vi.unstubAllGlobals();
    expect(fetchMock).toHaveBeenCalledWith("/api/terms", expect.objectContaining({
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ terms_version: "terms-v1", privacy_version: "privacy-v1" }),
    }));
  });
  it("reloads the page, without an error, when the versions have changed (409)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 409 })));
    const reload = vi.fn();
    render(<TermsStep reload={reload} versions={versions} />);
    await userEvent.click(screen.getByRole("button", { name: "I agree and continue" }));
    vi.unstubAllGlobals();
    expect(reload).toHaveBeenCalledOnce();
    expect(screen.queryByText("Something went wrong. Try again.")).not.toBeInTheDocument();
  });
  it("reloads after accepting", async () => {
    const reload = vi.fn();
    render(<TermsStep accept={vi.fn().mockResolvedValue(undefined)} reload={reload} versions={versions} />);
    await userEvent.click(screen.getByRole("button", { name: "I agree and continue" }));
    expect(reload).toHaveBeenCalledOnce();
  });
  it("says so and keeps the form when accepting fails", async () => {
    const reload = vi.fn();
    render(<TermsStep accept={vi.fn().mockRejectedValue(new Error("x"))} reload={reload} versions={versions} />);
    await userEvent.click(screen.getByRole("button", { name: "I agree and continue" }));
    expect(await screen.findByText("Something went wrong. Try again.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "I agree and continue" })).toBeEnabled();
    expect(reload).not.toHaveBeenCalled();
  });
  it("links the terms and the privacy notice, states age and versions", () => {
    render(<TermsStep accept={vi.fn()} reload={() => {}} versions={versions} />);
    expect(screen.getAllByRole("link", { name: "terms of use" })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "terms of use" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "privacy notice" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByText(/you are 18 or older/)).toBeInTheDocument();
    expect(screen.getByText("Terms terms-v1, privacy notice privacy-v1.")).toBeInTheDocument();
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
  it("does not allow a second send after success", async () => {
    const send = vi.fn().mockResolvedValue(undefined);
    render(<NotRecognised send={send} />);
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Thank you. We will look at it.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
    expect(send).toHaveBeenCalledOnce();
  });
  it("does not mark the note invalid when the server fails", async () => {
    render(<NotRecognised send={vi.fn().mockRejectedValue(new Error("x"))} />);
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("Something went wrong. Try again.");
    expect(screen.getByLabelText("Tell us what happened")).not.toHaveAttribute("aria-invalid");
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

describe("welcomeState", () => {
  it("passes the member to the view", async () => {
    const me = await meOf("bo");
    expect(await welcomeState(() => Promise.resolve(me), null)).toEqual({ kind: "free", checking: false });
  });
  it("sends an unauthenticated visitor to sign in", async () =>
    expect(await welcomeState(() => Promise.reject(new ApiError(401, "unauthenticated", "x")), null)).toEqual({ kind: "signin" }));
  it.each([
    new ApiError(503, "unavailable", "x"),
    new ApiError(403, "forbidden", "x"),
    new TypeError("network"),
  ])("says the service could not be reached for %s", async (error) =>
    expect(await welcomeState(() => Promise.reject(error), null)).toEqual({ kind: "unavailable" }));
});

describe("WelcomeBody", () => {
  it("offers a retry when the service could not be reached", () => {
    render(<WelcomeBody view={{ kind: "unavailable" }} />);
    expect(screen.getByRole("heading", { name: "We could not reach the service. Try again." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Try again" })).toHaveAttribute("href", "/welcome");
  });
  it.each([
    { kind: "terms" as const, versions: { terms: "terms-v1", privacy: "privacy-v1" } },
    { kind: "paid" as const, grantUntil: "2027-01-31T00:00:00Z", includedWhilePaying: true },
    { kind: "free" as const, checking: false },
    { kind: "other_plan" as const, planInterval: "month" as const },
  ])("offers Sign out in the $kind view", (view) => {
    render(<WelcomeBody view={view} />);
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
  it("shows the guarantee date in the paid view", () => {
    render(<WelcomeBody view={{ kind: "paid", grantUntil: "2027-01-31T00:00:00Z", includedWhilePaying: false }} />);
    expect(screen.getByText("Your access is guaranteed until 31 January 2027.")).toBeInTheDocument();
  });
});

describe("WelcomeBody other_plan", () => {
  it("shows the monthly plan with both links and no recognition form", () => {
    render(<WelcomeBody view={{ kind: "other_plan", planInterval: "month" }} />);
    expect(screen.getByRole("heading", { name: "You are on the monthly plan." })).toBeInTheDocument();
    expect(screen.getByText("Full access to the platform comes with the annual plan.")).toBeInTheDocument();
    expect(screen.getByText("Until you change your plan, you have the free workspace.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See how to change your plan" })).toHaveAttribute("href", "/upgrade");
    expect(screen.getByRole("link", { name: "Open your workspace" })).toHaveAttribute("href", "/member");
    expect(screen.queryByText("Paying on Substack already?")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
  it("omits the annual-plan sentence for the annual plan", () => {
    render(<WelcomeBody view={{ kind: "other_plan", planInterval: "year" }} />);
    expect(screen.getByRole("heading", { name: "You are on the annual plan." })).toBeInTheDocument();
    expect(screen.queryByText("Full access to the platform comes with the annual plan.")).not.toBeInTheDocument();
  });
});

describe("SignOutButton", () => {
  beforeEach(() => localStorage.clear());
  it("signs out, forgets the stored address and goes to /join", async () => {
    localStorage.setItem("signin.email", "ana@example.org");
    const go = vi.fn();
    const signOut = vi.fn().mockResolvedValue(undefined);
    render(<SignOutButton signOut={signOut} go={go} />);
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(signOut).toHaveBeenCalledOnce();
    expect(go).toHaveBeenCalledWith("/join");
    expect(localStorage.getItem("signin.email")).toBeNull();
  });
  it("goes to /join even when the sign-out fails", async () => {
    const go = vi.fn();
    render(<SignOutButton signOut={vi.fn().mockRejectedValue(new Error("x"))} go={go} />);
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(go).toHaveBeenCalledWith("/join");
  });
});
