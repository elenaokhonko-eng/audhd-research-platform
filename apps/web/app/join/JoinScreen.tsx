"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AuthError,
  createFakeAuthClient,
  createFirebaseAuthClient,
  toAuthError,
  type AuthClient,
} from "@/lib/identity/auth-client";
import type { IdentityConfig } from "@/lib/identity/config";
import type { Campaign } from "@/lib/platform-api/types";

export type JoinScreenProps = {
  campaign: Campaign;
  slug: string | null;
  siteOrigin: string;
  senderHint: string | null;
  identity: IdentityConfig;
  authClient?: AuthClient;
  postSession?: (idToken: string, campaign: string | null) => Promise<{ next: string }>;
  navigate?: (url: string) => void;
};

export function continueUrl(siteOrigin: string, slug: string | null): string {
  return slug ? `${siteOrigin}/auth/finish?c=${slug}` : `${siteOrigin}/auth/finish`;
}

async function defaultPostSession(idToken: string, campaign: string | null): Promise<{ next: string }> {
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id_token: idToken, campaign }),
  });
  if (response.status !== 200) throw new Error("session_failed");
  return (await response.json()) as { next: string };
}

const defaultNavigate = (url: string) => window.location.assign(url);

type Phase = "idle" | "sending" | "sent";

export function JoinScreen({
  campaign,
  slug,
  siteOrigin,
  senderHint,
  identity,
  authClient,
  postSession = defaultPostSession,
  navigate = defaultNavigate,
}: JoinScreenProps) {
  const client = useMemo<AuthClient | null>(() => {
    if (identity.kind === "missing") return null;
    if (authClient) return authClient;
    if (identity.kind === "fake") return createFakeAuthClient();
    if (identity.kind === "firebase") {
      return createFirebaseAuthClient({ apiKey: identity.apiKey, authDomain: identity.authDomain });
    }
    return null;
  }, [authClient, identity]);

  const [email, setEmail] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [invalid, setInvalid] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const liveRef = useRef<HTMLDivElement>(null);
  const focusTarget = useRef<"input" | "live" | null>(null);

  useEffect(() => {
    const target = focusTarget.current;
    focusTarget.current = null;
    if (target === "input") inputRef.current?.focus();
    if (target === "live") liveRef.current?.focus();
  });

  if (campaign.state !== "open") {
    return (
      <section className="section-shell join">
        <p className="section-kicker">Join</p>
        <h1>Opening soon</h1>
        <p>{campaign.copy.body}</p>
      </section>
    );
  }

  const sendLink = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!client || busy) return;
    const address = email.trim();
    if (!address.includes("@")) {
      setMessage("Check the email address.");
      setInvalid(true);
      inputRef.current?.focus();
      return;
    }
    setMessage("");
    setInvalid(false);
    setBusy(true);
    try {
      try {
        localStorage.setItem("signin.email", address);
      } catch {
        // Private mode: not storing the address must not stop the link being sent.
      }
      await client.sendEmailLink(address, continueUrl(siteOrigin, slug));
      focusTarget.current = "live";
      setPhase("sent");
    } catch (error) {
      if (toAuthError(error).code === "invalid_email") {
        setMessage("Check the email address.");
        setInvalid(true);
        focusTarget.current = "input";
      } else {
        setMessage("Something went wrong. Try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    if (!client || busy) return;
    setMessage("");
    setBusy(true);
    try {
      const token = await client.signInWithGoogle();
      const { next } = await postSession(token, slug);
      navigate(next);
    } catch (error) {
      if (error instanceof AuthError && error.code === "popup_closed") {
        setBusy(false);
        return;
      }
      setMessage("Something went wrong. Try again.");
      setBusy(false);
    }
  };

  const reset = () => {
    setEmail("");
    setMessage("");
    setInvalid(false);
    focusTarget.current = "input";
    setPhase("idle");
  };

  return (
    <section className="section-shell join">
      <p className="section-kicker">Join</p>
      <h1>{campaign.copy.headline}</h1>
      <p>{campaign.copy.body}</p>
      {client === null ? (
        <p>Sign-in is not set up in this environment.</p>
      ) : (
        <>
          {phase === "sent" ? (
            <div>
              <button className="button button-secondary" disabled={busy} onClick={reset} type="button">
                Use a different email
              </button>
            </div>
          ) : (
            <form noValidate onSubmit={sendLink}>
              <label htmlFor="join-email">Email address</label>
              <input
                autoComplete="email"
                aria-describedby={invalid ? "join-status" : undefined}
                aria-invalid={invalid ? "true" : undefined}
                id="join-email"
                inputMode="email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                ref={inputRef}
                type="email"
                value={email}
              />
              <div className="button-row">
                <button className="button button-primary" disabled={busy} type="submit">
                  Email me a sign-in link
                </button>
              </div>
            </form>
          )}
          <div className="button-row">
            <button className="button button-secondary" disabled={busy} onClick={google} type="button">
              Continue with Google
            </button>
          </div>
        </>
      )}
      <div aria-live="polite" id="join-status" ref={liveRef} role="status" tabIndex={-1}>
        {phase === "sent" ? (
          <>
            <p>Check your inbox.</p>
            {senderHint ? <p>The email comes from {senderHint}.</p> : null}
            <p>If it is not there after a minute, look in the spam folder or use Continue with Google.</p>
          </>
        ) : null}
        {message ? <p>{message}</p> : null}
      </div>
      <p>
        <Link href="/terms">Terms</Link> · <Link href="/privacy">Privacy notice</Link>
      </p>
    </section>
  );
}
