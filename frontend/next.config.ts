import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Small self-contained build for the Docker image
  output: "standalone",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
