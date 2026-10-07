import type { NextConfig } from "next";

import { createNextConfig } from "../../../shared/next-config.mjs";

// Served by the API server at /chat.
const nextConfig: NextConfig = createNextConfig({ basePath: "/chat" });

export default nextConfig;
