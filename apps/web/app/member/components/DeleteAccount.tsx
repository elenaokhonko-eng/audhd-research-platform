"use client";

import { useEffect, useRef, useState } from "react";

export function DeleteAccount({ onDone = () => window.location.assign("/") }: { onDone?: () => void }) {
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const openRef = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef(false);

  useEffect(() => {
    if (asking) cancelRef.current?.focus();
    else if (returnFocus.current) {
      returnFocus.current = false;
      openRef.current?.focus();
    }
  }, [asking]);

  async function confirm() {
    if (busy) return;
    setBusy(true);
    setFailed(false);
    try {
      const res = await fetch("/api/account/delete", { method: "POST" });
      if (!res.ok) throw new Error("failed");
      onDone();
    } catch {
      setFailed(true);
      setBusy(false);
    }
  }

  if (!asking) {
    return (
      <div>
        <button
          className="button button-secondary"
          onClick={() => {
            setFailed(false);
            setAsking(true);
          }}
          ref={openRef}
          type="button"
        >
          Delete my account
        </button>
      </div>
    );
  }
  return (
    <div>
      <p>Delete your account? You will be signed out now.</p>
      <div className="button-row">
        <button className="button button-primary" disabled={busy} onClick={confirm} type="button">
          Yes, delete it
        </button>
        <button
          className="button button-secondary"
          onClick={() => {
            returnFocus.current = true;
            setAsking(false);
          }}
          ref={cancelRef}
          type="button"
        >
          Cancel
        </button>
      </div>
      {failed ? <p role="alert">That did not work. Please try again.</p> : null}
    </div>
  );
}
