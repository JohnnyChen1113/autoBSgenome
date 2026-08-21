import { createFileRoute } from "@tanstack/react-router";

import skillText from "../../../skills/autobsgenome/SKILL.md?raw";

export const Route = createFileRoute("/skill.md")({
  server: {
    handlers: {
      GET: async () =>
        new Response(skillText, {
          headers: {
            "cache-control": "public, max-age=300",
            "content-type": "text/markdown; charset=utf-8",
          },
        }),
    },
  },
});
