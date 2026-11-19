"use client";

import { useState } from "react";
import { defaultSignOut, leaveToJoin } from "@/lib/identity/sign-out";

class SendError extends Error {
  constructor(readonly status: number) {
    super("support request failed");
  }
}

async function defaultSend(note: string): Promise<void> {
  const res = await fetch("/api/support", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ note }),
  });
  if (!res.ok) throw new SendError(res.status);
}

export function NotRecognised({
  send = defaultSend,
  signOut = defaultSignOut,
  go = (url: string) => window.location.assign(url),
}: {
  send?: (note: string) => Promise<void>;
  signOut?: () => Promise<void>;
  go?: (url: string) => void;
}) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(false);

  const another = () => leaveToJoin(signOut, go);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      await send(note);
      setDone(true);
      setMessage("Thank you. We will look at it.");
    } catch (error) {
      setMessage(
        (error as { status?: number }).status === 409 ? "Accept the terms first." : "Something went wrong. Try again.",
      );
    }
    setBusy(false);
  };

  return (
    <section>
      <h2>Paying on Substack already?</h2>
      <p>Sign in with the email address your newsletter arrives at.</p>
      <div className="button-row">
        <button className="button button-secondary" onClick={another} type="button">
          Sign in with another email
        </button>
      </div>
      {done ? null : (
      <form onSubmit={submit}>
        <label htmlFor="support-note">Tell us what happened</label>
        <textarea
          aria-describedby="support-status"
          id="support-note"
          maxLength={500}
          name="note"
          onChange={(event) => setNote(event.target.value)}
          rows={4}
          value={note}
        />
        <div className="button-row">
          <button className="button button-primary" disabled={busy} type="submit">
            Send
          </button>
        </div>
      </form>
      )}
      <div aria-live="polite" id="support-status" role="status">
        {message ? <p>{message}</p> : null}
      </div>
    </section>
  );
}
