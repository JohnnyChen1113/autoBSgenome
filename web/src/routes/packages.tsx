import { createFileRoute } from "@tanstack/react-router";

import PackagesPage from "@/features/packages/PackagesPage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/packages")({
  head: () =>
    seoHead({
      title: "BSgenome Package Repository - AutoBSgenome",
      description:
        "Search BSgenome R packages by organism, assembly, accession, provider, and taxonomy. Copy warning-free R install commands for each package directly.",
      path: "/packages",
      keywords:
        "BSgenome package repository, install BSgenome, BSgenome packages, Bioconductor genome package, NCBI BSgenome, Ensembl BSgenome",
    }),
  component: PackagesPage,
});
