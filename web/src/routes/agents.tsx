import { createFileRoute } from "@tanstack/react-router";

import AgentsPage from "@/features/agents/AgentsPage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/agents")({
  head: () =>
    seoHead({
      title: "AutoBSgenome for AI Agents and Coding Tools",
      description:
        "Use AutoBSgenome with Claude Code, Cursor, and other AI tools to find BSgenome packages, trigger builds, poll status, and return R install commands.",
      path: "/agents",
      keywords:
        "AutoBSgenome agent, BSgenome AI agent, Claude Code BSgenome, Cursor bioinformatics, AI coding tools genomics",
    }),
  component: AgentsPage,
});
