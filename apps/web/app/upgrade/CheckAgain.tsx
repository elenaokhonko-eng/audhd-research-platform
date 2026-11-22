"use client";

import { useState } from "react";
import { pollUntilPaid } from "@/lib/upgrade";

const timer = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function CheckAgain({
  sleep = timer,
  onPaid = () => window.location.reload(),
}: {
  sleep?: (ms: number) => Promise<void>;
  onPaid?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function run() {
    setBusy(true);
    setMessage("");
    try {
      let started: Response;
      try {
        started = await fetch("/api/refresh-access", { method: "POST" });
      } catch {
        setMessage("The check could not be started. Please try again in a minute.");
        return;
      }
      if (started.status === 429) {
        setMessage("Please wait a moment before checking again.");
        return;
      }
      if (!started.ok) {
        setMessage("The check could not be started. Please try again in a minute.");
        return;
      }
      setMessage("Checking with Substack's payment records…");
      const outcome = await pollUntilPaid({
        sleep,
        tier: async () => {
          const res = await fetch("/api/tier");
          if (res.status === 401) return "signed_out";
          if (!res.ok) throw new Error("not yet");
          const body = (await res.json()) as { tier?: string };
          return body.tier === "paid" ? "paid" : "free";
        },
      });
      if (outcome === "paid") {
        onPaid();
      } else if (outcome === "signed_out") {
        window.location.assign("/join");
      } else {
        setMessage(
          "We did not find a paid subscription for this address yet. If you subscribed with another email address, sign in with that one, or use Tell us on the welcome page.",
        );
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="check-again">
      <button className="button button-primary" disabled={busy} onClick={run} type="button">
        Check again
      </button>
      <p role="status">{message}</p>
    </div>
  );
}
