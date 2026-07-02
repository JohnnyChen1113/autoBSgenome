import { createFileRoute } from "@tanstack/react-router";

import { siteConfig } from "@/config";

export const Route = createFileRoute("/robots.txt")({
  server: {
    handlers: {
      GET: async () => {
        const origin = siteConfig.url.replace(/\/$/, "");
        return new Response(
          `User-agent: *\nAllow: /\n\nSitemap: ${origin}/sitemap.xml\nHost: ${origin.replace(/^https?:\/\//, "")}\n`,
          {
            headers: {
              "content-type": "text/plain; charset=utf-8",
            },
          }
        );
      },
    },
  },
});
