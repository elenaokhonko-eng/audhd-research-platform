"use client";

import Link from "next/link";
import { useState } from "react";

type Shown = { terms_version: string; privacy_version: string };

// A 409 means the required versions changed since the page was drawn.
async function defaultAccept(shown: Shown): Promise<void> {
  const res = await fetch("/api/terms", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(shown),
  });
  if (!res.ok) throw Object.assign(new Error("terms failed"), { status: res.status });
}

export function TermsStep({
  versions,
  accept = defaultAccept,
  reload = () => window.location.reload(),
}: {
  versions: { terms: string; privacy: string };
  accept?: (shown: Shown) => Promise<void>;
  reload?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      await accept({ terms_version: versions.terms, privacy_version: versions.privacy });
    } catch (error) {
      if ((error as { status?: number }).status === 409) return reload();
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
          Please read the <Link href="/terms">terms of use</Link> and the <Link href="/privacy">privacy notice</Link>.
        </p>
        <p>By continuing you confirm that you are 18 or older and that you agree to both.</p>
        <p>
          Terms {versions.terms}, privacy notice {versions.privacy}.
        </p>
        <div className="button-row">
          <button className="button button-primary" disabled={busy} type="submit">
            I agree and continue
          </button>
        </div>
      </form>
      <div aria-live="polite" role="status">
        {message ? <p>{message}</p> : null}
      </div>
    </section>
  );
}
