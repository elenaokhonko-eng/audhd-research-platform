"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { refusalText } from "@/lib/library";

export function DownloadButton({
  sku,
  onUrl = (url: string) => window.location.assign(url),
  navigate = (to: string) => window.location.assign(to),
}: {
  sku: string;
  onUrl?: (url: string) => void;
  navigate?: (to: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<ReturnType<typeof refusalText> | null>(null);
  const running = useRef(false);

  async function run() {
    if (running.current) return;
    running.current = true;
    setBusy(true);
    setRefusal(null);
    try {
      let res: Response;
      try {
        res = await fetch(`/api/library/${encodeURIComponent(sku)}/download`, { method: "POST" });
      } catch {
        setRefusal(refusalText(503, null));
        return;
      }
      if (res.status === 401) return navigate("/join");
      if (res.status === 409) return navigate("/welcome");
      if (res.status === 200) {
        const body = (await res.json().catch(() => null)) as { url?: unknown } | null;
        if (body && typeof body.url === "string") return onUrl(body.url);
        setRefusal(refusalText(503, null));
        return;
      }
      const body = (await res.json().catch(() => null)) as { reason?: unknown } | null;
      setRefusal(refusalText(res.status, typeof body?.reason === "string" ? body.reason : null));
    } finally {
      running.current = false;
      setBusy(false);
    }
  }

  return (
    <>
      <button className="button button-secondary" disabled={busy} onClick={run} type="button">
        Download
      </button>
      {refusal ? (
        <p role="alert">
          {refusal.text} {refusal.link ? <Link href={refusal.link.href}>{refusal.link.label}</Link> : null}
        </p>
      ) : null}
    </>
  );
}
