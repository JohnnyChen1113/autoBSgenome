# Build performance optimization backlog

Last updated: 2026-08-22

This document records performance ideas that are intentionally separate from
the correctness and product-policy backlog in `BUILD-PIPELINE-DECISIONS.md`.

## Product decision: no build-time accession deduplication

The backend must not reject or silently reuse a package merely because the
same `provider + accession.version` already exists. Administrators and
benchmark campaigns may deliberately rebuild an accession. The Web UI may
show an existing-package notice before submission, but that notice must remain
advisory and must not change the requested build.

## Measured baseline

The optimized no-publish build of the 9.35-Gbp `GCA_963921465.1` assembly used
run `32561399985`:

| Stage | Elapsed |
|---|---:|
| NCBI download and extraction | 4 min 48 s |
| FASTA inspection | 4 s |
| FASTA to 2bit | 1 min 04 s |
| Forge | 11 s |
| R CMD build | 1 min 34 s |
| Archive validation | 26 s |
| Workflow start to tarball | 7 min 42 s |
| Complete GitHub job | 8 min 44 s |

Download/extraction, 2bit conversion, and package assembly therefore dominate
the remaining critical path.

## Implement now: NCBI FASTA streaming to 2bit

The NCBI fast path should resolve the accession's official Genomes FTP
`*_genomic.fna.gz` file and its published MD5, then process one data stream:

```text
NCBI HTTPS response (gzip)
  -> compressed-byte MD5
  -> gzip decompression and integrity check
  -> FASTA structure/statistics inspection
  -> faToTwoBit stdin
  -> genome.2bit
```

Acceptance criteria:

- no `genome.zip` or uncompressed `genome.fa` is materialized on the fast path;
- FASTA byte count, record count, and first five IDs come from the same stream;
- the compressed stream must match NCBI's MD5 and pass gzip integrity checks;
- a truncated HTTP response, invalid gzip, invalid FASTA, inspection failure, or
  `faToTwoBit` failure must fail the attempt and remove partial output;
- HTTP retries restart the entire stream instead of appending a retry to a
  partially consumed stdout stream;
- assemblies above the existing size threshold retain `faToTwoBit -long`;
- NCBI Datasets ZIP download remains a compatibility fallback when FTP
  resolution or all streaming attempts fail;
- metrics identify `ncbi-ftp-stream` versus `ncbi-datasets-fallback` and record
  compressed bytes, uncompressed FASTA bytes, total stream time, and 2bit size;
- benchmark mode still skips every publication path and deletes the tarball.

The first production comparison should reuse `GCA_963921465.1` with
`publish_to_index=false`.

## Deferred: parallel package compression

Add `pigz` to a future builder image and compare current `R CMD build`, parallel
gzip at its default level, and a faster compression level. Measure build time,
tarball size, installation, package loading, and sequence retrieval. Packages
near the GitHub 1.9-GiB threshold may need a stronger compression policy than
benchmark or Zenodo-bound packages.

Do not replace `R CMD build` with direct tar assembly until archive contents and
install/load behavior have been shown equivalent on both small and very large
packages.

## Deferred: checksum and archive validation in one pass

The archive validation stage currently decompresses the tarball to list its
members and then reads it again for SHA-256. A future implementation can tee a
single compressed stream into SHA-256 and parallel decompression/member
validation. Keep the validation gate; optimize its I/O only.

## Deferred: short-lived 2bit cache

A cache keyed by provider, accession version, upstream checksum, `faToTwoBit`
mode, and builder version could skip acquisition and conversion during failed
retries or deliberate benchmark reruns. It should be limited to internal or
curated workflows and governed by an R2 lifecycle because multi-gigabyte 2bit
objects make an unrestricted cache expensive.

This cache must not become hidden build deduplication: a requested build still
runs the package-generation and archive stages.

## Deferred: finer timing instrumentation

Record network transfer, ZIP validation, extraction/decompression, package
copying, and gzip compression separately. Install GNU `time` in the builder so
the existing `R CMD build` resource capture actually produces its report.

## Not currently justified: warm self-hosted runners

A warm runner could avoid roughly 30 seconds of container initialization, but
it adds security isolation, maintenance, scaling, and reproducibility costs.
Reconsider only after streaming and compression work is measured at campaign
scale.
