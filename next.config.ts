import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  typedRoutes: true,
  output: 'export',
  basePath: process.env.GITHUB_ACTIONS ? '/loudmusic-audio-analysis' : undefined,
};

export default nextConfig;
