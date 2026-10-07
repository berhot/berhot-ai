import type { NextConfig } from "next";

import { createNextConfig } from "../../../shared/next-config.mjs";

// Served by the API server at /.
const nextConfig: NextConfig = createNextConfig();

export default nextConfig;
