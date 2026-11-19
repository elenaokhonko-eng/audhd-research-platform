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

describe("JoinScreen accessibility", () => {
  it("announces the confirmation in the live region and moves focus to it", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText("Email address"), "ana@example.org");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    const live = await screen.findByRole("status");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveTextContent("Check your inbox.");
    expect(live).toHaveFocus();
  });

  it("returns focus to the email field after Use a different email", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText("Email address"), "ana@example.org");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    await user.click(await screen.findByRole("button", { name: "Use a different email" }));
    expect(screen.getByLabelText("Email address")).toHaveFocus();
    expect(screen.getByLabelText("Email address")).toHaveValue("");
  });

  it("marks the field invalid, links the message and focuses the field", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText("Email address"), "ana");
    await user.click(screen.getByRole("button", { name: "Email me a sign-in link" }));
    const field = screen.getByLabelText("Email address");
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveFocus();
    const id = field.getAttribute("aria-describedby");
    expect(id).toBeTruthy();
    expect(document.getElementById(id as string)).toHaveTextContent("Check the email address.");
  });
});
