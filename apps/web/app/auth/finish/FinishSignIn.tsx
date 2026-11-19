"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toAuthError, type AuthClient } from "@/lib/identity/auth-client";
import type { IdentityConfig } from "@/lib/identity/config";
import {
  buildAuthClient,
  defaultPostSession,
  isRetryable,
  type PostSession,
} from "@/lib/identity/session-client";
import { cleanSlug } from "@/lib/slug";

export type FinishProps = {
  identity: IdentityConfig;
  href?: string;
  authClient?: AuthClient;
  postSession?: PostSession;
  navigate?: (url: string) => void;
};

export function slugFromHref(href: string): string | null {
  try {
    const params = new URL(href).searchParams;
    const direct = cleanSlug(params.get("c"));
    if (direct) return direct;
    const inner = params.get("continueUrl");
    return inner ? cleanSlug(new URL(inner).searchParams.get("c")) : null;
  } catch {
    return null;
  }
}

function forgetEmail(): void {
  try {
    localStorage.removeItem("signin.email");
  } catch {
    // Storage unavailable: nothing to remove.
  }
}

// The sign-in page is not worth keeping in history: replace it.
const replaceNavigate = (url: string): void => window.location.replace(url);

type Phase = "working" | "ask" | "expired" | "retry";

export function FinishSignIn({
  identity,
  href: hrefProp,
  authClient,
  postSession = defaultPostSession,
  navigate = replaceNavigate,
}: FinishProps) {
  const client = useMemo(() => buildAuthClient(identity, authClient), [authClient, identity]);
  const [href, setHref] = useState<string | null>(hrefProp ?? null);
  const [phase, setPhase] = useState<Phase>("working");
  const [email, setEmail] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const tokenRef = useRef<string | null>(null); // memory only: never storage, URL or log
  const started = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const liveRef = useRef<HTMLDivElement>(null);
  const focusTarget = useRef<"input" | "live" | null>(null);

  const captured = useRef<string | null>(hrefProp ?? null);

  useEffect(() => {
    // Keep the link in memory, then take the single-use code out of the address
    // bar, history and Referer. Captured once, so a second effect run (StrictMode)
    // never reads the cleaned address.
    if (captured.current === null) captured.current = window.location.href;
    setHref(captured.current);
    const slugOnly = slugFromHref(captured.current);
    window.history.replaceState(null, "", slugOnly ? `/auth/finish?c=${slugOnly}` : "/auth/finish");
  }, []);

  useEffect(() => {
    const target = focusTarget.current;
    focusTarget.current = null;
    if (target === "input") inputRef.current?.focus();
    if (target === "live") liveRef.current?.focus();
  });

  const slug = href ? slugFromHref(href) : null;
  const isLink = client && href ? client.isEmailLink(href) : null;

  const exchange = async (token: string) => {
    setBusy(true);
    setMessage("");
    setPhase("working");
    try {
      const { next } = await postSession(token, slug);
      forgetEmail();
      navigate(next);
    } catch (error) {
      focusTarget.current = "live";
      setBusy(false);
      if (isRetryable(error)) {
        setPhase("retry");
      } else {
        // The token was refused: sending it again cannot work, so offer a new link.
        tokenRef.current = null;
        forgetEmail();
        setPhase("expired");
      }
    }
  };

  const complete = async (address: string) => {
    if (!client || !href) return;
    setBusy(true);
    setMessage("");
    setInvalid(false);
    setPhase("working");
    let token: string;
    try {
      token = await client.completeEmailLink(address, href);
    } catch (error) {
      const code = toAuthError(error).code;
      setBusy(false);
      if (code === "link_expired" || code === "link_used") {
        forgetEmail();
        focusTarget.current = "live";
        setPhase("expired");
      } else {
        setPhase("ask");
        if (code === "invalid_email") {
          setMessage("Check the email address.");
          setInvalid(true);
          focusTarget.current = "input";
        } else {
          setMessage("Something went wrong. Try again.");
        }
      }
      return;
    }
    tokenRef.current = token;
    await exchange(token);
  };

  useEffect(() => {
    // An oobCode is single-use, so this runs once per page load, even when
    // StrictMode runs effects twice.
    if (started.current || !client || !href || !isLink) return;
    started.current = true;
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("signin.email");
    } catch {
      // Private mode: ask for the address instead.
    }
    if (stored) void complete(stored);
    else setPhase("ask");
  }, [client, href, isLink]);

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) return;
    const address = email.trim();
    if (!address) {
      setMessage("Check the email address.");
      setInvalid(true);
      inputRef.current?.focus();
      return;
    }
    void complete(address);
  };

  const retry = () => {
    if (busy || !tokenRef.current) return;
    void exchange(tokenRef.current);
  };

  let body: React.ReactNode;
  if (client === null) {
    body = <p>Sign-in is not set up in this environment.</p>;
  } else if (isLink === false) {
    body = (
      <>
        <p>This page finishes a sign-in link.</p>
        <p>
          <Link href={slug ? `/join/${slug}` : "/join"}>Start again</Link>
        </p>
      </>
    );
  } else if (phase === "ask") {
    body = (
      <form noValidate onSubmit={submit}>
        <p id="finish-hint">Type the email address the link was sent to.</p>
        <label htmlFor="finish-email">Email address</label>
        <input
          aria-describedby={invalid ? "finish-status finish-hint" : "finish-hint"}
          aria-invalid={invalid ? "true" : undefined}
          autoComplete="email"
          id="finish-email"
          inputMode="email"
          name="email"
          onChange={(event) => setEmail(event.target.value)}
          ref={inputRef}
          type="email"
          value={email}
        />
        <div className="button-row">
          <button className="button button-primary" disabled={busy} type="submit">
            Finish signing in
          </button>
        </div>
      </form>
    );
  } else {
    body = null;
  }

  const showStatus = client !== null && isLink !== false && href !== null;
  return (
    <section className="section-shell join">
      <p className="section-kicker">Sign in</p>
      <h1>Finish signing in</h1>
      {body}
      <div aria-live="polite" id="finish-status" ref={liveRef} role="status" tabIndex={-1}>
        {showStatus && phase === "working" ? <p>Signing you in.</p> : null}
        {showStatus && phase === "expired" ? (
          <>
            <p>This link has expired or was already used.</p>
            <p>
              <Link href={slug ? `/join/${slug}` : "/join"}>Send me a new link</Link>
            </p>
          </>
        ) : null}
        {showStatus && phase === "retry" ? (
          <>
            <p>We could not reach the service. Try again.</p>
            <button className="button button-primary" disabled={busy} onClick={retry} type="button">
              Try again
            </button>
          </>
        ) : null}
        {showStatus && message ? <p>{message}</p> : null}
      </div>
    </section>
  );
}
