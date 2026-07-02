import { createFileRoute } from "@tanstack/react-router";

import { siteConfig, sitePaths } from "@/config";

const pagePriority: Record<string, string> = {
  "/": "1.0",
  "/packages": "0.95",
  "/build": "0.95",
  "/help": "0.8",
  "/api-docs": "0.75",
  "/agents": "0.75",
};

const pageChangeFrequency: Record<string, string> = {
  "/": "weekly",
  "/packages": "daily",
  "/build": "weekly",
  "/help": "monthly",
  "/api-docs": "monthly",
  "/agents": "monthly",
};

export const Route = createFileRoute("/sitemap.xml")({
  server: {
    handlers: {
      GET: async () => {
        const origin = siteConfig.url.replace(/\/$/, "");
        const lastmod = new Date().toISOString().slice(0, 10);
        const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitePaths
  .map(
    (path) => `  <url>
    <loc>${origin}${path === "/" ? "/" : path}</loc>
    <lastmod>${lastmod}</lastmod>
    <changefreq>${pageChangeFrequency[path] ?? "weekly"}</changefreq>
    <priority>${pagePriority[path] ?? "0.7"}</priority>
  </url>`
  )
  .join("\n")}
</urlset>`;
        return new Response(body, {
          headers: {
            "content-type": "application/xml; charset=utf-8",
          },
        });
      },
    },
  },
});
