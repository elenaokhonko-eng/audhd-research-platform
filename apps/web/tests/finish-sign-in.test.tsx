import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { renderToString } from "react-dom/server";
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
  it("is null for a broken address", () => expect(slugFromHref("not a url")).toBeNull());
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

  it("flags an empty email", async () => {
    const { postSession, user } = setup(LINK);
    await user.click(screen.getByRole("button", { name: "Finish signing in" }));
    expect(await screen.findByText("Check the email address.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toHaveAttribute("aria-invalid", "true");
    expect(postSession).not.toHaveBeenCalled();
  });

  it("flags an email the service rejects and keeps the form usable", async () => {
    const authClient = createFakeAuthClient();
    const { AuthError } = await import("@/lib/identity/auth-client");
    authClient.completeEmailLink = vi.fn().mockRejectedValue(new AuthError("invalid_email"));
    const user = userEvent.setup();
    render(<FinishSignIn identity={{ kind: "fake" }} href={LINK} authClient={authClient} postSession={vi.fn()} navigate={vi.fn()} />);
    await user.type(screen.getByLabelText("Email address"), "bo@example.org");
    await user.click(screen.getByRole("button", { name: "Finish signing in" }));
    expect(await screen.findByText("Check the email address.")).toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Finish signing in" })).toBeEnabled();
  });

  it("shows a general error for other failures and keeps the form usable", async () => {
    const authClient = createFakeAuthClient();
    const { AuthError } = await import("@/lib/identity/auth-client");
    authClient.completeEmailLink = vi.fn().mockRejectedValue(new AuthError("network"));
    const user = userEvent.setup();
    render(<FinishSignIn identity={{ kind: "fake" }} href={LINK} authClient={authClient} postSession={vi.fn()} navigate={vi.fn()} />);
    await user.type(screen.getByLabelText("Email address"), "bo@example.org");
    await user.click(screen.getByRole("button", { name: "Finish signing in" }));
    expect(await screen.findByText("Something went wrong. Try again.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finish signing in" })).toBeEnabled();
  });

  it.each(["expired", "used"])("explains a link that is %s and offers a new one for the same campaign", async (code) => {
    localStorage.setItem("signin.email", "ana@example.org");
    const { postSession } = setup(`https://dev.example.org/auth/finish?c=founding&oobCode=${code}`);
    expect(await screen.findByText("This link has expired or was already used.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Send me a new link" })).toHaveAttribute("href", "/join/founding");
    expect(postSession).not.toHaveBeenCalled();
    expect(localStorage.getItem("signin.email")).toBeNull();
  });

  it("offers the plain join page when there is no campaign", async () => {
    localStorage.setItem("signin.email", "ana@example.org");
    setup("https://dev.example.org/auth/finish?oobCode=expired");
    expect(await screen.findByRole("link", { name: "Send me a new link" })).toHaveAttribute("href", "/join");
  });

  it("retries with the same token when the service was unreachable", async () => {
    localStorage.setItem("signin.email", "ana@example.org");
    const postSession = vi.fn().mockRejectedValueOnce(new Error("503")).mockResolvedValueOnce({ next: "/welcome" });
    const { navigate, user } = setup(LINK, postSession);
    expect(await screen.findByText("We could not reach the service. Try again.")).toBeInTheDocument();
    expect(localStorage.getItem("signin.email")).toBe("ana@example.org");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("/welcome"));
    expect(postSession).toHaveBeenNthCalledWith(2, "fake-token:ana", "founding");
  });

  it("completes the link only once under StrictMode", async () => {
    localStorage.setItem("signin.email", "ana@example.org");
    const authClient = createFakeAuthClient();
    const complete = vi.spyOn(authClient, "completeEmailLink");
    const postSession = vi.fn().mockResolvedValue({ next: "/welcome" });
    const navigate = vi.fn();
    render(
      <StrictMode>
        <FinishSignIn identity={{ kind: "fake" }} href={LINK} authClient={authClient} postSession={postSession} navigate={navigate} />
      </StrictMode>,
    );
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledTimes(1));
    expect(complete).toHaveBeenCalledTimes(1);
    expect(postSession).toHaveBeenCalledTimes(1);
  });

  it("says what the page is for when opened without a link", () => {
    setup("https://dev.example.org/auth/finish");
    expect(screen.getByText("This page finishes a sign-in link.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start again" })).toHaveAttribute("href", "/join");
  });

  it("shows no form when sign-in is not set up", () => {
    render(<FinishSignIn identity={{ kind: "missing" }} href={LINK} />);
    expect(screen.getByText("Sign-in is not set up in this environment.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("removes the single-use code from the address bar after mount, keeping the slug", () => {
    const spy = vi.spyOn(window.history, "replaceState");
    setup(LINK);
    expect(spy).toHaveBeenCalledWith(null, "", "/auth/finish?c=founding");
    spy.mockRestore();
  });

  it("reads the real address by default, still completes with it, then cleans it", async () => {
    window.history.replaceState(null, "", "/auth/finish?c=founding&oobCode=ok&mode=signIn");
    localStorage.setItem("signin.email", "ana@example.org");
    const spy = vi.spyOn(window.history, "replaceState");
    const navigate = vi.fn();
    const postSession = vi.fn().mockResolvedValue({ next: "/welcome" });
    render(<FinishSignIn identity={{ kind: "fake" }} authClient={createFakeAuthClient()} postSession={postSession} navigate={navigate} />);
    await vi.waitFor(() => expect(navigate).toHaveBeenCalledWith("/welcome"));
    expect(postSession).toHaveBeenCalledWith("fake-token:ana", "founding");
    expect(spy).toHaveBeenCalledWith(null, "", "/auth/finish?c=founding");
    expect(window.location.search).toBe("?c=founding");
    spy.mockRestore();
  });

  it("shows nothing in the status region before the address is known", () => {
    const html = renderToString(<FinishSignIn identity={{ kind: "fake" }} authClient={createFakeAuthClient()} />);
    expect(html).not.toContain("Signing you in.");
  });
});
