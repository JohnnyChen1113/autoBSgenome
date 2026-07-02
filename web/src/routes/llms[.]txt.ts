import { createFileRoute } from "@tanstack/react-router";

import { siteConfig } from "@/config";

export const Route = createFileRoute("/llms.txt")({
  server: {
    handlers: {
      GET: async () => {
        const origin = siteConfig.url.replace(/\/$/, "");
        const body = `# AutoBSgenome

AutoBSgenome is a web service and API for building, browsing, and installing BSgenome R packages for genomics and Bioconductor workflows.

## Core URLs
- Website: ${origin}/
- Package browser: ${origin}/packages
- Online builder: ${origin}/build
- API documentation: ${origin}/api-docs
- Agent guide: ${origin}/agents
- Hosted skill file: ${origin}/skill.md
- Package download domain: https://packages.autobsgenome.org

## What AutoBSgenome Does
- Builds BSgenome source packages from NCBI assembly accessions, Ensembl species URLs, FASTA download URLs, and local nucleotide FASTA uploads.
- Provides a searchable BSgenome package repository with package metadata, accession links, taxonomy, install commands, and tarball downloads.
- Runs builds through GitHub Actions and returns temporary package tarballs.
- Uses warning-free R install commands that first download a tarball to a local temporary file, then run install.packages() on that file.

## Recommended Agent Behavior
1. Search ${origin}/packages first.
2. If an exact package exists for the requested organism, assembly, and accession, return the package card's R install command.
3. If no exact package exists, use ${origin}/api-docs to trigger a build through the public API.
4. Poll build status until complete or failed.
5. Return the final one-line R install command.
6. Do not publish user-triggered builds to the permanent repository. Permanent package index inclusion is maintainer-curated.

## Keywords
BSgenome, Bioconductor, R package, reference genome, NCBI, Ensembl, FASTA, genome package builder, bioinformatics, genomics
`;
        return new Response(body, {
          headers: {
            "content-type": "text/plain; charset=utf-8",
          },
        });
      },
    },
  },
});
