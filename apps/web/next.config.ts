import type { NextConfig } from "next";

// `standalone` produces a self-contained server (.next/standalone/server.js)
// so the container needs no node_modules install at runtime. Cloud Run sets PORT.
const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
};

export default nextConfig;
