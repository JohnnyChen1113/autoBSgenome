# Domain Context

## Local Build CLI

The Local Build CLI preserves AutoBSgenome's original workflow: it builds a
BSgenome package on the user's machine with local R, BSgenomeForge, and
`faToTwoBit`. It is not a command-line client for the hosted build queue.

## Metadata Entry Modes

The Local Build CLI has two metadata entry modes:

- **Automatic metadata entry** accepts an NCBI or Ensembl assembly accession,
  species identifier, or official NCBI/Ensembl page URL. It retrieves known
  metadata, prefills every supported wizard field, and lets the user accept or
  edit each value.
- **Manual metadata entry** is used for all other sources. The CLI does not
  attempt to infer structured genome metadata from arbitrary websites.

Automatic metadata entry may use official upstream metadata from NCBI and
Ensembl, but the package is still built locally. If upstream lookup fails, the
CLI preserves any values already collected and lets the user complete the
remaining fields manually.

After metadata review, users choose between downloading the official upstream
FASTA and selecting a local FASTA file. NCBI and Ensembl official downloads
use their public HTTPS genome archives and are verified against upstream
checksums when available. This choice does not change the local nature of the
package build.

## Genome Release Date

`release_date` means the upstream genome assembly release date. It must not
default to the day on which the BSgenome package is built. In manual mode the
user supplies this value explicitly.

## Build Draft

A Build Draft is the normalized, editable metadata collected before generating
the BSgenome seed file. NCBI and Ensembl source adapters produce Build Drafts;
the interactive wizard reviews them; the local builder consumes the confirmed
result.
