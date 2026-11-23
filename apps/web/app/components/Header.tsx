"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { PromotionBanner } from "./PromotionBanner";

const links = [
  ["Research", "/research-agenda"],
  ["Library", "/evidence-library"],
  ["Clinicians", "/clinician-resources"],
  ["Methods", "/methods"],
  ["About", "/about-elena-okhonko"],
] as const;

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" href="/" onClick={() => setOpen(false)}>
          <span className="brand-mark" aria-hidden="true">A</span>
          <span>AuDHD Research</span>
        </Link>
        <button
          aria-expanded={open}
          aria-label="Toggle navigation"
          className="menu-button"
          onClick={() => setOpen((value) => !value)}
          type="button"
        >
          <span />
          <span />
          <span />
        </button>
        <nav className={open ? "main-nav open" : "main-nav"} aria-label="Main navigation">
          {links.map(([label, href]) => (
            <Link
              className={pathname === href ? "active" : ""}
              href={href}
              key={href}
              onClick={() => setOpen(false)}
            >
              {label}
            </Link>
          ))}
          <Link className={pathname === "/ask" ? "active mobile-only" : "mobile-only"} href="/ask">
            Ask AuDHD Research
          </Link>
          <Link className={pathname === "/member" ? "active mobile-only" : "mobile-only"} href="/member">
            Member preview
          </Link>
        </nav>
        <div className="header-actions">
          <span className="language-label" title="English; additional languages planned">EN</span>
          <Link className="login-link" href="/member">Member preview</Link>
          <a
            className="button button-primary button-small"
            href="https://elenaokhonko.substack.com/subscribe"
            rel="noreferrer"
            target="_blank"
          >
            Join membership
          </a>
        </div>
      </div>
    </header>
    <PromotionBanner />
    </>
  );
}
