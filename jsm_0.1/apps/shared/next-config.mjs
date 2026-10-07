import path from "node:path";
import { fileURLToPath } from "node:url";

// The JSM API (python -m scripts.serve).
const API_URL = process.env.JSM_API_URL ?? "http://127.0.0.1:8000";

// Every app is a client of this one JSON API.
const API_ROUTES = [
  "/health",
  "/models",
  "/generate",
  "/admin/overview",
  "/admin/training/runs",
  "/admin/data/summary",
];

// apps/ — the npm workspace root, which also holds shared/.
const APPS_ROOT = path.dirname(
  path.dirname(fileURLToPath(import.meta.url)),
);

/**
 * Next.js config shared by every JSM web app.
 *
 * The apps always call the API with absolute paths ("/models").
 *
 * next dev   -> those paths are proxied to the API server.
 * next build -> static export into out/, which the API server
 *               serves under `basePath`.
 *
 * @param {{ basePath?: string }} options
 * @returns {import("next").NextConfig}
 */
export function createNextConfig({ basePath = "" } = {}) {
  const common = {
    basePath,
    trailingSlash: true,
    turbopack: { root: APPS_ROOT },
  };

  if (process.env.NODE_ENV !== "development") {
    return { ...common, output: "export" };
  }

  return {
    ...common,
    // Otherwise "/models" is redirected to "/models/" before the proxy.
    skipTrailingSlashRedirect: true,
    async rewrites() {
      return API_ROUTES.map((route) => ({
        source: route,
        destination: `${API_URL}${route}`,
        basePath: false,
      }));
    },
  };
}
