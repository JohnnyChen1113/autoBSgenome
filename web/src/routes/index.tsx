import { createFileRoute } from "@tanstack/react-router";

import HomePage from "@/features/home/HomePage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/")({
  head: () =>
    seoHead({
      title: "AutoBSgenome - Build and Browse BSgenome R Packages",
      description:
        "Build BSgenome R packages online from NCBI, Ensembl, FASTA URLs, or local nucleotide FASTA files, and browse installable AutoBSgenome packages for R and Bioconductor workflows.",
      path: "/",
      keywords:
        "AutoBSgenome, BSgenome, build BSgenome package, Bioconductor BSgenome, R genomics, NCBI genome, Ensembl genome",
    }),
  component: HomePage,
});
