"use client";

import { useState } from "react";
import { defaultSignOut, leaveToJoin } from "@/lib/identity/sign-out";

export function SignOutButton({
  signOut = defaultSignOut,
  go = (url: string) => window.location.assign(url),
}: {
  signOut?: () => Promise<void>;
  go?: (url: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  const leave = async () => {
    if (busy) return;
    setBusy(true);
    await leaveToJoin(signOut, go);
  };

  return (
    <div className="button-row">
      <button className="button button-secondary" disabled={busy} onClick={leave} type="button">
        Sign out
      </button>
    </div>
  );
}
