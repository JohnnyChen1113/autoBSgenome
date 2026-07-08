import { createFileRoute } from "@tanstack/react-router";

import ApiDocsPage from "@/features/api-docs/ApiDocsPage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/api-docs")({
  head: () =>
    seoHead({
      title: "AutoBSgenome API Documentation",
      description:
        "Use the AutoBSgenome API to trigger BSgenome builds, upload nucleotide FASTA files, poll GitHub Actions status, and delete temporary releases.",
      path: "/api-docs",
      keywords:
        "AutoBSgenome API, BSgenome build API, FASTA upload API, GitHub Actions genome package build",
    }),
  component: ApiDocsPage,
});
