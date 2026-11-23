import Link from "next/link";
import { cardActions, KIND_LABEL } from "@/lib/library";
import type { ItemCard } from "@/lib/platform-api/types";
import { DownloadButton } from "./DownloadButton";

export function ItemAction({ item }: { item: ItemCard }) {
  const actions = cardActions(item);
  return (
    <>
      {actions.map((action) => {
        if (action.kind === "download") return <DownloadButton key="download" sku={item.sku} />;
        if (action.kind === "buy")
          return (
            <span key="buy">
              <a aria-describedby={`new-tab-note-${item.sku}`} href={action.url} rel="noreferrer" target="_blank">
                Buy
              </a>{" "}
              <span id={`new-tab-note-${item.sku}`}>Opens in a new tab.</span>{" "}
            </span>
          );
        return (
          <Link href="/upgrade" key="upgrade">
            Upgrade to open
          </Link>
        );
      })}
    </>
  );
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
