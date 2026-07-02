import { createFileRoute } from "@tanstack/react-router";

import BuildPage from "@/features/build/BuildPage";
import { seoHead } from "@/lib/seo";

export const Route = createFileRoute("/build")({
  head: () =>
    seoHead({
      title: "Build BSgenome Packages Online - AutoBSgenome",
      description:
        "Create a ready-to-install BSgenome R package from an NCBI accession, Ensembl species URL, FASTA download URL, or local nucleotide FASTA upload.",
      path: "/build",
      keywords:
        "build BSgenome online, create BSgenome package, NCBI accession to BSgenome, Ensembl BSgenome, FASTA to BSgenome",
    }),
  component: BuildPage,
});
