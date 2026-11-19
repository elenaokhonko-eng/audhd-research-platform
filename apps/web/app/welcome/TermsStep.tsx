"use client";

import Link from "next/link";
import { useState } from "react";

async function defaultAccept(): Promise<void> {
  const res = await fetch("/api/terms", { method: "POST" });
  if (!res.ok) throw new Error("terms failed");
}

export function TermsStep({
  accept = defaultAccept,
  reload = () => window.location.reload(),
}: {
  accept?: () => Promise<void>;
  reload?: () => void;
}) {
  const [ticked, setTicked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ticked || busy) return;
    setBusy(true);
    setMessage("");
    try {
      await accept();
    } catch {
      setMessage("Something went wrong. Try again.");
      setBusy(false);
      return;
    }
    reload();
  };

  return (
    <section className="section-shell join">
      <h1>Before you start</h1>
      <form onSubmit={submit}>
        <p>
          <input
            checked={ticked}
            id="accept-terms"
            name="accept"
            onChange={(event) => setTicked(event.target.checked)}
            type="checkbox"
          />{" "}
          <label htmlFor="accept-terms">
            I have read and accept the <Link href="/terms">terms</Link> and the{" "}
            <Link href="/privacy">privacy notice</Link>
          </label>
        </p>
        <div className="button-row">
          <button className="button button-primary" disabled={!ticked || busy} type="submit">
            Continue
          </button>
        </div>
      </form>
      <div aria-live="polite" role="status">
        {message ? <p>{message}</p> : null}
      </div>
    </section>
  );
}
