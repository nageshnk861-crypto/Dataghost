/** @type {import('next').NextConfig} */
const backendUrl = (
  process.env.BACKEND_INTERNAL_URL ||
  process.env.BACKEND_URL ||
  (process.env.NODE_ENV === "production"
    ? "https://t1zzc9hp-8000.inc1.devtunnels.ms"
    : "http://127.0.0.1:8000")
).replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/docs",
        destination: `${backendUrl}/docs`,
      },
      {
        source: "/openapi.json",
        destination: `${backendUrl}/openapi.json`,
      },
      {
        source: "/dataghost-agent.apk",
        destination: `${backendUrl}/dataghost-agent.apk`,
      },
    ];
  },
};

module.exports = nextConfig;

