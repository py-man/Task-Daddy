/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@neonlanes/shared"],
  async rewrites() {
    const api = process.env.API_INTERNAL_URL || "http://api:8000";
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  }
};

export default nextConfig;
