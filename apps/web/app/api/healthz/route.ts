// Liveness endpoint for Cloud Run probes and the uptime check. No dependencies, no data.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({
    status: "ok",
    service: "web",
    env: process.env.SITE_ENV ?? "unknown",
    revision: process.env.K_REVISION ?? "local",
  });
}
