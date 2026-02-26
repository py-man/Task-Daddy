export async function GET() {
  const version = process.env.NEXT_PUBLIC_APP_VERSION || "v2026-02-26+r3-hardening";
  const buildSha = process.env.NEXT_PUBLIC_BUILD_SHA || process.env.BUILD_SHA || "dev";
  return Response.json({ version, buildSha });
}
