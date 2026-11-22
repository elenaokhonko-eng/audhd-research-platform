"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type Offer = { badge: string; headline: string };

// Fetched after the page loads, because public pages are built ahead of time. Shows nothing on any failure.
export function PromotionBanner() {
  const [offer, setOffer] = useState<Offer | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const res = await fetch("/api/promotions");
        if (!res.ok) return;
        const list: unknown = await res.json();
        const first = Array.isArray(list) ? (list[0] as Offer | undefined) : undefined;
        if (live && first && typeof first.badge === "string" && typeof first.headline === "string") setOffer(first);
      } catch {
        // Nothing is shown.
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  if (!offer) return null;
  return (
    <p className="promotion-banner">
      <strong>{offer.badge}</strong> {offer.headline} <Link href="/upgrade">See the offer</Link>
    </p>
  );
}
