/** @type {import('next').NextConfig} */

// Where the FastAPI backend lives. The browser talks only to this Next.js server (same origin),
// which proxies /api/v1/* here — so no CORS and no build-time API URL in the client bundle.
// Read at build time: change it and rebuild (Render redeploys automatically on env changes).
const BACKEND_URL = (process.env.BACKEND_URL || "http://localhost:8000").replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  poweredByHeader: false,
  // Free-tier backends can take ~50s to wake from sleep; don't fail proxied requests at 30s.
  experimental: {
    proxyTimeout: 120_000
  },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${BACKEND_URL}/api/v1/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" }
        ]
      }
    ];
  }
};

export default nextConfig;
