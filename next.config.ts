import type { NextConfig } from 'next'
import path from 'path'

const nextConfig: NextConfig = {
  // There is a stray package-lock.json in the home folder. Without this,
  // Next.js walks up and warns about it on every start.
  turbopack: {
    root: path.join(__dirname),
  },
}

export default nextConfig
