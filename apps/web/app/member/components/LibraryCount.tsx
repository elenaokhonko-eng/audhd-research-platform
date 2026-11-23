import Link from "next/link";
import type { LibraryCounts } from "@/lib/library";

export function LibraryCount({ counts, tier }: { counts: LibraryCounts | null; tier: "free" | "paid" }) {
  if (!counts || counts.total === 0) return null;
  const all = tier === "paid" && counts.open === counts.total;
  const items = counts.total === 1 ? "1 item" : `${counts.total} items`;
  return (
    <p>
      {`The library has ${items}. You can open ${all ? "all" : counts.open} of them.`}
      {tier === "free" && counts.open < counts.total ? (
        <>
          {" "}
          <Link href="/upgrade">See how to open the rest</Link>
        </>
      ) : null}
    </p>
  );
}
