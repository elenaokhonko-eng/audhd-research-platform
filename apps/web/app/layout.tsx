import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://audhdneurobiology.org"),
  title: {
    default: "AuDHD Origins & Biology Research",
    template: "%s | AuDHD Research",
  },
  description:
    "Independent research into the biological, developmental, hormonal, metabolic and evolutionary dimensions of co-occurring autism and ADHD.",
  keywords: [
    "AuDHD research",
    "autism and ADHD",
    "AuDHD biology",
    "AuDHD hormones",
    "neurodivergent research",
  ],
  openGraph: {
    title: "AuDHD Origins & Biology Research",
    description:
      "Evidence maps for the integrated biology and development of co-occurring autism and ADHD.",
    type: "website",
    locale: "en_GB",
    siteName: "AuDHD Research",
  },
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
