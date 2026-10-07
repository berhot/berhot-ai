import type { NextConfig } from "next";

import { createNextConfig } from "../../../shared/next-config.mjs";

// Served by the API server at /admin.
const nextConfig: NextConfig = createNextConfig({ basePath: "/admin" });

export default nextConfig;
