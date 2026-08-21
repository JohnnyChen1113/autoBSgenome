---
name: autobsgenome
description: Find, build, and install BSgenome R packages from NCBI, Ensembl, or nucleotide FASTA sources. Use when a user needs a BSgenome package, has a missing-genome error, or is preparing an R/Bioconductor genomics workflow that depends on BSgenome.
---

# AutoBSgenome

Use AutoBSgenome's public HTTP API directly. No MCP server is required.

## Workflow

1. Identify the exact organism, assembly, provider, and accession the user needs.
2. Search existing packages before building:
   - AutoBSgenome packages: `https://johnnychen1113.github.io/autoBSgenome/packages.json`
   - Bioconductor packages: `https://johnnychen1113.github.io/autoBSgenome/bioc-packages.json`
   - Buildable catalog: `https://johnnychen1113.github.io/autoBSgenome/catalog.json`
3. Reuse an existing package only when its organism, assembly, and accession match. Prefer an exact Bioconductor package, then an exact AutoBSgenome package.
4. If no exact package exists, submit one build to `POST https://api.autobsgenome.org/api/build`.
5. Poll `GET https://api.autobsgenome.org/api/status/{job_id}` every 10 seconds until `complete` or `failed`. Stop after 65 minutes and return the job ID plus workflow URL instead of polling forever.
6. Return the package identity, source accession, install command, and cleanup deadline.

## Build Requests

Use the API reference at `https://autobsgenome.org/api-docs` for the complete schema.

For NCBI builds, send a `GCF_` accession when an equivalent RefSeq assembly exists. Include at least `package_name`, `organism`, `accession`, `data_source`, and `version`.

For Ensembl builds, set `data_source` to `ensembl` and include the Ensembl `species_url` slug and `ensembl_group`.

For a user-supplied FASTA URL or upload, state that the finished package is a temporary public download. Do not submit private or sensitive sequence data without the user's explicit confirmation that public temporary hosting is acceptable.

Do not invent metadata. If organism, assembly, provider, or accession cannot be verified, ask for the missing information before triggering a build.

## Completion and Installation

A completed response includes `download_url`, `retention_days`, and `scheduled_cleanup_after`. Tell the user that the server-hosted tarball is public and scheduled for cleanup approximately two days after completion.

Install by downloading to a local file first:

```r
local({options(timeout = 7200); url <- "DOWNLOAD_URL"; tarball <- tempfile(fileext = ".tar.gz"); on.exit(unlink(tarball), add = TRUE); download.file(url, tarball, mode = "wb", method = "libcurl"); install.packages(tarball, repos = NULL, type = "source")})
```

Clarify that the local temporary file in this R command is separate from the server-hosted download. Advise the user to save a local copy if the package will be needed after `scheduled_cleanup_after`.

On failure, report the exact API message, `job_id`, package metadata, and `workflow_run_url` when present. Do not silently resubmit.

## Boundaries

- Do not build when an exact existing package is available.
- Do not claim a package was installed unless installation was actually run and verified.
- Do not look for delete or permanent-publish operations; the public API intentionally provides neither.
- Do not expose signed upload URLs or other user-specific values beyond the current task.
