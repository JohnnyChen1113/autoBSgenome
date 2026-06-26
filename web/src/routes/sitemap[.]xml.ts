import { createFileRoute } from "@tanstack/react-router";

import { siteConfig, sitePaths } from "@/config";

export const Route = createFileRoute("/sitemap.xml")({
  server: {
    handlers: {
      GET: async () => {
        const origin = siteConfig.url.replace(/\/$/, "");
        const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitePaths
  .map((path) => `  <url><loc>${origin}${path === "/" ? "/" : path}</loc></url>`)
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
