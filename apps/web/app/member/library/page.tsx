import { ItemList } from "../components/ItemList";
import { loadView } from "@/lib/library";
import { requireMember, sessionForRequest } from "@/lib/member";
import { getPlatformApi } from "@/lib/platform-api/client";

export const dynamic = "force-dynamic";

export default async function Page() {
  const result = await loadView(
    "all",
    () => requireMember("library"),
    sessionForRequest,
    (session) => getPlatformApi().libraryItems(session),
  );
  return (
    <main>
      <h1>Library</h1>
      {result.kind === "items" ? <ItemList items={result.items} /> : <p role="status">{result.text}</p>}
    </main>
  );
}
