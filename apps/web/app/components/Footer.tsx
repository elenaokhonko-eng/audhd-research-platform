import Link from "next/link";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="section-shell footer-grid">
        <div>
          <Link className="footer-brand" href="/">AuDHD Origins &amp; Biology Research</Link>
          <p>
            Independent, neuroinclusive research into the integrated biology and
            development of co-occurring autism and ADHD.
          </p>
        </div>
        <div className="footer-links">
          <a href="https://elenaokhonko.substack.com/" rel="noreferrer" target="_blank">Substack ↗</a>
          <Link href="/methods#ethics">Ethics</Link>
          <Link href="/about-elena-okhonko#contact">Contact</Link>
          <Link href="/methods#privacy">Privacy</Link>
        </div>
        <div className="footer-meta">
          <span>© 2026 AuDHD Origins &amp; Biology Research</span>
          <span>Independent research project · Singapore</span>
        </div>
      </div>
    </footer>
  );
}
