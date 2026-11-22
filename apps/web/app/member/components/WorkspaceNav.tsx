"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function WorkspaceNav({ items }: { items: { href: string; label: string }[] }) {
  const path = usePathname();
  const current = (href: string) => (href === "/member" ? path === href : path === href || path.startsWith(`${href}/`));
  return (
    <nav aria-label="Member navigation">
      {items.map((item) => (
        <Link aria-current={current(item.href) ? "page" : undefined} className={current(item.href) ? "active" : ""} href={item.href} key={item.href}>
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
