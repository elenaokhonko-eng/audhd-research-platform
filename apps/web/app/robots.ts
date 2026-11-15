import type { MetadataRoute } from "next";

// Read at request time so the same image can run as dev (not indexed) and prod (indexed).
export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  if (process.env.SITE_ENV !== "prod") {
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/member", "/ask"] },
    sitemap: "https://audhdneurobiology.org/sitemap.xml",
  };
}
