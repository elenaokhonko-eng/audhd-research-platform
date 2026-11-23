"use client";

import { useEffect, useRef, useState } from "react";
import { pollUntilPaid } from "@/lib/upgrade";

const timer = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function CheckAgain({
  sleep = timer,
  onPaid = () => window.location.reload(),
  navigate = (to: string) => window.location.assign(to),
}: {
  sleep?: (ms: number) => Promise<void>;
  onPaid?: () => void;
  navigate?: (to: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const running = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  async function run() {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setMessage("");
    const say = (text: string) => {
      if (alive.current) setMessage(text);
    };
    let termsRequired = false;
    try {
      let started: Response;
      try {
        started = await fetch("/api/refresh-access", { method: "POST" });
      } catch {
        say("The check could not be started. Please try again in a minute.");
        return;
      }
      if (started.status === 401) {
        navigate("/join");
        return;
      }
      if (started.status === 409) {
        navigate("/welcome");
        return;
      }
      if (started.status === 429) {
        say("Please wait a moment before checking again.");
        return;
      }
      if (!started.ok) {
        say("The check could not be started. Please try again in a minute.");
        return;
      }
      say("Checking with Substack's payment records…");
      const outcome = await pollUntilPaid({
        sleep: async (ms) => {
          if (alive.current) await sleep(ms);
        },
        tier: async () => {
          if (!alive.current) return "signed_out";
          const res = await fetch("/api/tier");
          if (res.status === 401) return "signed_out";
          if (res.status === 409) {
            termsRequired = true;
            return "signed_out";
          }
          if (!res.ok) throw new Error("not yet");
          const body = (await res.json()) as { tier?: string };
          return body.tier === "paid" ? "paid" : "free";
        },
      });
      if (!alive.current) return;
      if (outcome === "paid") {
        onPaid();
      } else if (outcome === "signed_out") {
        navigate(termsRequired ? "/welcome" : "/join");
      } else {
        say(
          "We did not find a paid subscription for this address yet. If you subscribed with another email address, sign in with that one, or use Tell us on the welcome page.",
        );
      }
    } finally {
      running.current = false;
      if (alive.current) setBusy(false);
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
