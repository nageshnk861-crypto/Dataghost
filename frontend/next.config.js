/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = (process.env.BACKEND_INTERNAL_URL || process.env.BACKEND_URL || "").trim().replace(/\/+$/, "");
    if (!backendUrl || backendUrl.includes("devtunnels.ms")) {
      return [];
    }
    return [
      {
        source: "/dataghost-agent.apk",
        destination: `${backendUrl}/dataghost-agent.apk`,
      },
    ];
  },
};

module.exports = nextConfig;
