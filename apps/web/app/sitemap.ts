import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = ["", "/research-agenda", "/evidence-library", "/clinician-resources", "/methods", "/about-elena-okhonko"];
  return routes.map((route) => ({ url: `https://audhdneurobiology.org${route}`, lastModified: new Date("2026-08-02"), changeFrequency: route === "" ? "weekly" : "monthly", priority: route === "" ? 1 : 0.8 }));
}
