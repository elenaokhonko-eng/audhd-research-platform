import { notFound } from "next/navigation";
import { loadItem, missingItemText, KIND_LABEL, SKU_PATTERN } from "@/lib/library";
import { requireMember, sessionForRequest } from "@/lib/member";
import { getPlatformApi } from "@/lib/platform-api/client";
import { ItemAction } from "../../components/ItemList";

export const dynamic = "force-dynamic";

export default async function LibraryItem({ params }: { params: Promise<{ sku: string }> }) {
  const { sku } = await params;
  const result = await loadItem(
    sku,
    () => requireMember("library"),
    sessionForRequest,
    (session) => getPlatformApi().libraryItem(session, sku),
  );
  if (result.kind === "not_found") {
    if (!SKU_PATTERN.test(sku)) notFound();
    const text = await missingItemText(sessionForRequest, (session) => getPlatformApi().libraryItems(session));
    return (
      <main>
        <h1>Library</h1>
        <p role="status">{text}</p>
      </main>
    );
  }
  if (result.kind === "message")
    return (
      <main>
        <h1>Library</h1>
        <p role="status">{result.text}</p>
      </main>
    );
  const { item, description, citation } = result.detail;
  return (
    <main>
      <h1>{item.title}</h1>
      <p>
        {KIND_LABEL[item.kind]}, version {item.version}
        {item.pages !== 0 ? `, ${item.pages} pages` : ""}
      </p>
      <p>{description}</p>
      {citation ? <p>{citation}</p> : null}
      <ItemAction item={item} />
    </main>
  );
}
