import { ItemList } from "../components/ItemList";
import { LibraryCount } from "../components/LibraryCount";
import { libraryCounts, loadView } from "@/lib/library";
import { requireMember, sessionForRequest } from "@/lib/member";
import { getPlatformApi } from "@/lib/platform-api/client";

export const dynamic = "force-dynamic";

export default async function Page() {
  let tier: "free" | "paid" = "free";
  const result = await loadView(
    "all",
    async () => {
      tier = (await requireMember("library")).access.tier;
    },
    sessionForRequest,
    (session) => getPlatformApi().libraryItems(session),
  );
  return (
    <main>
      <h1>Library</h1>
      {result.kind === "items" ? (
        <>
          <LibraryCount counts={libraryCounts(result.items)} tier={tier} />
          <ItemList items={result.items} />
        </>
      ) : (
        <p role="status">{result.text}</p>
      )}
    </main>
  );
}
