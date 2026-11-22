import type { NextConfig } from "next";

// `standalone` produces a self-contained server (.next/standalone/server.js)
// so the container needs no node_modules install at runtime. Cloud Run sets PORT.
const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // The legal pages read content/legal/*.md at build time; keep the files in the standalone output too.
  outputFileTracingIncludes: {
    "/terms": ["./content/legal/*"],
    "/privacy": ["./content/legal/*"],
  },
};

export default nextConfig;
