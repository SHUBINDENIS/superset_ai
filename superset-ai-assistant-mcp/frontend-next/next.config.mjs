/** @type {import('next').NextConfig} */
const nextConfig = {
  httpAgentOptions: {
    // Avoid stale keep-alive sockets when proxying long-running assistant requests
    // to FastAPI through Next.js rewrites.
    keepAlive: false,
  },
  // Proxy API calls to the FastAPI backend so that auth cookies
  // are set on the same origin (localhost:3000) as the frontend.
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8100";
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
