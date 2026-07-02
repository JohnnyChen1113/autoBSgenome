import { createFileRoute } from "@tanstack/react-router";

import ApiDocsPage from "@/features/api-docs/ApiDocsPage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/api-docs")({
  head: () =>
    seoHead({
      title: "AutoBSgenome API Documentation",
      description:
        "Programmatic API documentation for triggering BSgenome builds, uploading nucleotide FASTA files, polling GitHub Actions build status, and deleting temporary build releases.",
      path: "/api-docs",
      keywords:
        "AutoBSgenome API, BSgenome build API, FASTA upload API, GitHub Actions genome package build",
    }),
  component: ApiDocsPage,
});
