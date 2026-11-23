import Link from "next/link";
import { cardAction, KIND_LABEL } from "@/lib/library";
import type { ItemCard } from "@/lib/platform-api/types";
import { DownloadButton } from "./DownloadButton";

export function ItemAction({ item }: { item: ItemCard }) {
  const action = cardAction(item);
  if (action.kind === "download") return <DownloadButton sku={item.sku} />;
  if (action.kind === "buy")
    return (
      <>
        <a aria-describedby={`new-tab-note-${item.sku}`} href={action.url} rel="noreferrer" target="_blank">
          Buy
        </a>{" "}
        <span id={`new-tab-note-${item.sku}`}>Opens in a new tab.</span>
      </>
    );
  if (action.kind === "upgrade") return <Link href="/upgrade">Upgrade to open</Link>;
  return null;
}

export function ItemList({ items }: { items: ItemCard[] }) {
  return (
    <ul>
      {items.map((item) => (
        <li key={item.sku}>
          <h2>
            <Link href={`/member/library/${item.sku}`}>{item.title}</Link>
          </h2>
          <p>{KIND_LABEL[item.kind]}</p>
          <p>{item.abstract}</p>
          <ItemAction item={item} />
        </li>
      ))}
    </ul>
  );
}
