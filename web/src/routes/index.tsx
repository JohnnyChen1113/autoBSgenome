import { createFileRoute } from "@tanstack/react-router";

import HomePage from "@/features/home/HomePage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/")({
  head: () =>
    seoHead({
      title: "AutoBSgenome - Build and Browse BSgenome R Packages",
      description:
        "Build BSgenome R packages online from NCBI, Ensembl, FASTA URLs, and local FASTA uploads. Search packages and install them in R genomics workflows.",
      path: "/",
      keywords:
        "AutoBSgenome, BSgenome, build BSgenome package, Bioconductor BSgenome, R genomics, NCBI genome, Ensembl genome",
    }),
  component: HomePage,
});
