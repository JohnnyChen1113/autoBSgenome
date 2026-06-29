# Package Metadata Cleanup Backlog

This document records repository-browser metadata issues that should be fixed
together, rather than as one-off UI patches.

## 1. Genome Release Dates

Observed example:

- `BSgenome.Athaliana.Ensembl.TAIR10`
  - accession: `GCA_000001735.1`
  - current `packages.json`: no `release_date`, no `published`
  - UI therefore does not show "Genome release"
- `BSgenome.Athaliana.NCBI.TAIR101`
  - accession: `GCF_000001735.4`
  - current `packages.json`: `release_date: 2018-03-15`
  - UI shows "Genome release"

This is a data gap, not primarily a display bug. The browser only renders the
field when `release_date` exists.

Required fixes:

- Backfill `release_date` for all built packages from NCBI assembly summaries
  and, for missing accessions, the NCBI Datasets API.
- Include both `GCF_...` and `GCA_...` accessions. Ensembl packages often use
  `GCA_...`, so this must not be limited to `provider == "NCBI"`.
- Do not copy dates between related accessions. For example, `GCA_000001735.1`
  and `GCF_000001735.4` are related Arabidopsis assemblies but should be
  resolved independently.
- Add provenance, e.g. `release_date_source: "ncbi_assembly_summary"` or
  `release_date_source: "ncbi_datasets_api"`.
- Add an index-quality report with counts of built packages missing
  `release_date`, grouped by provider.

Also fix the frontend date formatter. The current `new Date("YYYY-MM-DD")`
path can render one day early in US time zones. Format plain date strings as
plain dates, without local-time conversion.

## 2. Ensembl Source URLs

Observed example:

- `BSgenome.Athaliana.Ensembl.TAIR10` currently points to
  `https://www.ensembl.org/Arabidopsis_thaliana/Info/Index`.
- Arabidopsis is an Ensembl Plants species, so the preferred species page should
  be on `plants.ensembl.org`, not the vertebrate-oriented `www.ensembl.org`
  host.

Required fixes:

- Re-audit existing Ensembl `source_url` values, not only empty values.
- Use taxonomy/group-aware subdomains:
  - plants -> `plants.ensembl.org`
  - fungi -> `fungi.ensembl.org`
  - metazoa/invertebrates -> `metazoa.ensembl.org`
  - protists/protozoa -> `protists.ensembl.org`
  - bacteria/archaea -> `bacteria.ensembl.org`
  - vertebrates/unknown -> `www.ensembl.org`
- Probe candidate URLs with a browser-like user agent, because Ensembl can
  return bot-blocking 403 responses to simple programmatic requests.
- Record unresolved cases as `_ensembl_status: "not_indexed"` only after
  probing the correct subdomain candidates.
- Update docs and examples that currently use plant examples on
  `www.ensembl.org`.

## 3. Assembly Names With Dots In Package Names

Observed example:

- Assembly: `TAIR10.1`
- Package: `BSgenome.Athaliana.NCBI.TAIR101`

This is intentional but not obvious. BSgenome package names use a
four-component dotted convention:

`BSgenome.<OrganismAbbrev>.<Provider>.<AssemblyToken>`

If the assembly token itself contains a dot, preserving it would create an
extra component and make the package name ambiguous. Therefore `TAIR10.1` is
normalized to `TAIR101` in the package name, while the displayed assembly remains
`TAIR10.1`.

Suggested UI note:

> Package name uses `TAIR101` because BSgenome package names must have exactly
> four dot-separated parts; the original assembly name is `TAIR10.1`.

Implementation approach:

- Add an index field such as `package_assembly_token` during package indexing,
  or compute it in the browser using the same normalization function used by the
  build pipeline.
- Show the note only when `assembly` differs from the final package assembly
  token.
- Keep the note compact and colocated with the assembly/package metadata, not
  inside the install command area.

## 4. Duplicate Bioconductor Links

Observed example:

- Bioconductor entries show a `Bioconductor` source chip near the package name.
- The same card also shows a lower `View on Bioconductor` link.

The lower link is redundant when the chip already links to the same
Bioconductor page.

Required fix:

- Keep the source chip as the canonical external link.
- Remove the lower `View on Bioconductor` link from Bioconductor package cards,
  unless a future design needs a separate secondary action.

## Acceptance Checks

- No built package displays a one-day-shifted release date.
- Missing `release_date` counts are reported and reduced after backfill.
- Plant Ensembl builds link to `plants.ensembl.org` when applicable.
- Packages with normalized assembly tokens explain the naming difference.
- Bioconductor cards show one external Bioconductor link, not two.
