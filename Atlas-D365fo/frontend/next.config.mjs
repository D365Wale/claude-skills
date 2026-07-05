/** @type {import('next').NextConfig} */
const backend = process.env.ATLAS_API_URL || "http://127.0.0.1:8321";

const nextConfig = {
  async rewrites() {
    // Proxy API calls through Next.js so the browser never needs CORS.
    return [{ source: "/atlas/:path*", destination: `${backend}/:path*` }];
  },
};

export default nextConfig;
