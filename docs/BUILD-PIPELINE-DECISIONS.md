# AutoBSgenome build pipeline and decision log

Last updated: 2026-09-08

The 2026-09-08 audit changes below have been deployed. Deployment versions and
hosted acceptance evidence are recorded in
[the pre-submission audit](PRE-SUBMISSION-CODE-AUDIT-2026-09-08.md).

This document describes the production build path from a browser request to an
installable BSgenome source package. It separates required package-building
work from validation, observability, storage, and publication policy so that
future changes can be made deliberately.

## Executive summary

The irreducible package-building path is:

```text
obtain FASTA
  -> convert FASTA to 2bit
  -> generate the BSgenome seed and package directory
  -> build a source tarball
  -> verify the archive
  -> retain it temporarily, publish it through a curated path, or delete it
```

Everything else exists to improve metadata quality, reject bad input, expose
progress, collect benchmark evidence, or enforce storage policy.

## End-to-end flow

```text
Web form / API client
  -> metadata review and package-name validation
  -> optional multipart FASTA upload to Cloudflare R2
  -> Cloudflare API Worker (`POST /api/build`)
  -> GitHub `repository_dispatch`
  -> pinned builder container on GitHub Actions
  -> one of four FASTA acquisition paths
       NCBI | Ensembl | URL | uploaded file
  -> fast FASTA inspection
       all sources: sequence count, first sequence IDs, file size
       URL/upload only: prefix-sampled format and nucleotide check
  -> `faToTwoBit`
  -> BSgenome seed (`circ_seqs: character(0)`)
  -> `forgeBSgenomeDataPkg()`
  -> `R CMD build`
  -> tar/gzip structure validation and SHA-256
  -> storage-policy branch
       temporary build | curated permanent build | benchmark
  -> status reporting and eventual cleanup
```

## 1. Browser and metadata preparation

The Web UI accepts an NCBI accession, an Ensembl species page, a user-hosted
FASTA URL, or a local FASTA upload. It prefills package name, organism, common
name, assembly, provider, release date, version, title, description, source URL,
and the FASTA source. Circular-sequence detection and user-editable circular
metadata have been removed; generated seeds use `circ_seqs: character(0)`.

Purpose:

- reduce manual metadata entry;
- enforce the four-part BSgenome package-name convention;
- make the FASTA source explicit before a build consumes runner resources.

Open improvements:

- move upstream metadata lookup behind the API Worker to reduce browser CORS
  and rate-limit failures;
- share one package-name and request schema between Web and Worker;
- revalidate authoritative metadata server-side instead of trusting every
  browser-supplied descriptive field.

## 2. User FASTA upload staging

Local files are uploaded in multipart chunks to a temporary Cloudflare R2
object. New upload/download signatures bind the declared byte size. The API
validates the part sequence and actual completed object size, then checks the
stored object again before dispatching a build. Invalid completed objects are
deleted; earlier signed URLs remain accepted. The build deletes the R2 object
after a successful download on a best-effort basis.

Purpose:

- bridge a browser-local file into GitHub Actions without exposing the R2
  bucket directly.

Open improvements:

- enforce an R2 lifecycle rule so abandoned uploads are removed even when a
  workflow fails before its DELETE request;
- detect gzip by magic bytes instead of filename extension;
- make maximum accepted size and expiry visible before upload begins.

## 3. API request validation and queue reporting

`POST /api/build` currently validates the required package and organism fields,
the package-name shape, NCBI accession URLs, Ensembl group values, URL schemes,
and signed upload URLs. It queries queued/running GitHub Actions jobs, generates
an eight-character job ID, and sends a `repository_dispatch` payload.

Purpose:

- reject obvious requests before allocating a build runner;
- provide a stable job ID for polling;
- isolate the public API from the R/Bioconductor build environment.

Open improvements:

- `MAX_QUEUE_SIZE=5` is currently informational; the Worker always accepts the
  request. Either enforce admission control or remove the misleading limit;
- use a longer job identifier to reduce collision risk;
- add rate limits or abuse controls for the unauthenticated public endpoint;
- restrict URL builds against private/loopback destinations, unsafe redirects,
  excessive response sizes, and unbounded downloads;
- replace GitHub Actions polling as the queue database with KV, D1, a Durable
  Object, or an event-driven status record.

## 4. Reproducible runner initialization

The build runs in a builder container pinned by digest on an Ubuntu GitHub
runner. The job hard timeout is 180 minutes. Benchmark payloads record a
60-minute core-build SLA, assembly metadata, runner hardware, stage timings,
memory, process RSS, and disk usage.

Purpose:

- keep R, BSgenome, NCBI Datasets, and UCSC tool versions reproducible;
- distinguish workflow failures from resource limits;
- make benchmark results auditable.

Open improvements:

- the 60-minute SLA is reported but not enforced as a separate timeout;
- sample resources less frequently, or only in benchmark mode, for ordinary
  builds;
- update JavaScript actions that still emit Node.js 20 deprecation warnings;
- estimate peak disk demand before downloading a very large assembly.

## 5. FASTA acquisition

### NCBI

The primary path resolves the versioned accession to the official NCBI Genomes
FTP `*_genomic.fna.gz`, its MD5, and assembly statistics. The compressed HTTPS
response is hashed and decompressed while the same FASTA byte stream is
inspected and fed to `faToTwoBit stdin`. This path never materializes a ZIP or
an uncompressed FASTA. Each network retry restarts the complete stream so a
partial response cannot be concatenated with a later attempt.

If FTP resolution or all three streaming attempts fail, the workflow retains
the previous NCBI Datasets ZIP path as a compatibility fallback. The fallback
materializes `genome.fa`, performs the same inspection, converts it, and then
removes the FASTA.

NCBI also documents a dehydrated-package and `datasets rehydrate` path for
large data packages. That path was evaluated and rejected: it adds another
metadata-package, unpack, and retrieval lifecycle without improving the primary
FTP stream or addressing converter memory. The direct Datasets ZIP remains the
compatibility fallback.

Resolution is a separate observable workflow step. Metrics distinguish
resolver wall time, total stream wall time, Python decompression/inspection
CPU, `faToTwoBit` CPU, attempt count, and fallback mode without splitting the
overlapping streaming pipeline into serial stages.

Potential improvements:

- compare streaming throughput across multiple GitHub runner regions;
- expose retry/fallback reasons in the public status response;
- add transfer-rate telemetry that remains meaningful under downstream
  backpressure.

### Ensembl

The workflow resolves the official FASTA URL from species/group information,
then streams the HTTP response through gzip/plain-format detection, FASTA
inspection, and `faToTwoBit stdin`. It does not materialize the compressed
download or an uncompressed `genome.fa`.

Potential improvements:

- cache resolver results;
- record and verify upstream checksum metadata.

Rejected performance proposal:

- do not replace the Python stream reader with native or parallel
  decompression.

### User URL

The workflow streams an HTTP/HTTPS resource directly through gzip/plain-format
detection, prefix-sampled validation, metadata inspection, and
`faToTwoBit stdin`.

Decision adopted in this revision:

- stop using `gzip -t` as format detection because it fully scans the archive
  before decompression and therefore reads compressed input twice;
- detect gzip from stream magic bytes and never materialize `genome.fa`.

### Uploaded file

The workflow streams the signed R2 object through gzip/plain-format detection,
prefix-sampled validation, metadata inspection, and `faToTwoBit stdin`. The
source R2 object is then deleted best-effort after successful consumption.

Decision adopted in this revision:

- use gzip magic bytes instead of trusting the filename suffix.
- never materialize an uncompressed `genome.fa`.

## 6. FASTA inspection

The former validator read every sequence character in Python, tested membership
in a nucleotide-character set, and then a second workflow step scanned the file
again for headers and sequence count. On the 9.35-Gbp *Triticum timopheevii*
assembly, validation alone took 13 minutes 13 seconds.

Decisions adopted in this revision:

- remove exhaustive per-character validation from every source;
- trust NCBI and Ensembl official FASTA enough to skip sampled character
  validation;
- for URL/upload inputs only, inspect a bounded prefix to reject obvious FASTQ,
  empty input, and protein/non-nucleotide input with a useful error;
- combine that lightweight check with sequence-ID/count/file-size collection;
- perform at most one full-file scan, using large binary chunks rather than a
  Python loop over every line or base.

The lightweight check is deliberately not a biological correctness audit. It
does not prove that an assembly matches its accession, detect duplicated
records, reproduce N50, or validate every byte of a user file. Successful
`faToTwoBit`, package construction, and archive verification remain downstream
compatibility gates.

Open decisions:

- whether custom URL/upload input needs a future compiled full validator;
- whether official-source sequence counts should be compared with NCBI/Ensembl
  metadata and how to handle organelle/unplaced-record differences.

## 7. FASTA to 2bit conversion

`faToTwoBit` converts sequence input to `genome.2bit`. Every primary source
arrives on stdin from a streaming pipeline. NCBI uses authoritative assembly
size metadata to select `-long`. For a custom stream whose uncompressed size is
unknown, the ordinary version-0 format is attempted first; only UCSC's specific
index-overflow result triggers one complete retry with `-long`.

A converter process that exits while its input pipe is being written is
reported by exit status or signal instead of being reduced to `Broken pipe`.
Confirmed cgroup OOM kills are identified explicitly. Converter failure is
terminal for that attempt and does not enter a different download path that
would invoke the same converter again.

Purpose:

- produce the compact indexed sequence representation consumed by BSgenome.

Potential improvements:

- validate the 12-GB heuristic against the actual 2bit addressing constraint;
- consider always selecting `-long` above a conservative assembly-size cutoff;
- expose the converter exit signal and confirmed OOM category in public build
  status.

## 8. Seed generation

The workflow writes package metadata and the 2bit location to a BSgenome seed.
Circular metadata is fixed to `character(0)`.

Purpose:

- describe the R package that BSgenomeForge must create.

Implemented in the 2026-09-08 audit:

- submitted Description reaches the seed, with a generated default when empty;
- parsed values enter shell steps through environment bindings, with no
  interpolation of step outputs into executable shell text;
- Python validates identifiers and single-line metadata before writing the
  seed. Control characters cannot introduce additional workflow outputs or
  DCF fields; shell metacharacters remain literal metadata.

## 9. Forge the package directory

The workflow invokes `BSgenomeForge::forgeBSgenomeDataPkg()` and places the
2bit file under `inst/extdata/single_sequences.2bit`.

Before forging, both paths prepare a separate seed that protects literal
`@...@` metadata from upstream template expansion. The original seed is retained
and its metadata is restored after forging, including whitespace in paths.
Before building, both hosted and CLI paths regenerate the R loader and Rd help
from installed BSgenomeForge templates, with context-specific literal escaping.
This prevents quotes in metadata from becoming R expressions and prevents Rd
`\Sexpr` directives in title/description from executing during the build.
R subprocesses also bypass startup profiles that could change the build
directory.

Purpose:

- create DESCRIPTION, NAMESPACE, R code, and the standard BSgenome package
  layout.

Open improvements:

- narrow the catch-all fallback so real metadata/forge errors are not masked as
  large-file copy failures.

Rejected performance proposal:

- do not replace BSgenomeForge's copy semantics with filesystem-dependent
  hardlinks or reflinks; measured forge time is too small to justify it.

## 10. Build the source tarball

`R CMD build` creates `Package_version.tar.gz`. The workflow forces external
GNU tar because R's built-in tar path cannot handle the largest 2bit members.
The unpacked package directory is removed after a successful build.

Purpose:

- produce the source package consumed by `install.packages(..., type="source")`.

Potential improvements:

- retain the current external-tar behavior for packages with members above the
  built-in tar limit.

Decision adopted:

- do not trade compression ratio for speed. Package size remains important,
  especially near GitHub's 2-GiB release-asset limit.

Rejected performance proposal:

- do not benchmark or substitute alternate gzip implementations, compression
  levels, or packaging profiles; retain the current `R CMD build` compressor.

## 11. Archive validation

The workflow reads the gzip/tar archive once. `tee` sends the compressed stream
to SHA-256 and `tar -tzf -`; validation requires DESCRIPTION and the 2bit
member.

Purpose:

- reject truncated archives and packages missing their essential data file;
- attach a reproducible integrity identifier.

This is a useful low-cost gate and should remain. It does not prove that R can
install and load the package. Curated permanent publication may eventually add
an install/load smoke test.

Rejected performance proposal:

- do not intercept archive creation to hash/validate concurrently and do not
  replace part of `R CMD build` with direct tar assembly. Post-build `tee`
  validation is the accepted optimization boundary.

## 12. Storage-policy branches

Tarballs below 1.9 GiB use GitHub Releases; larger tarballs select the Zenodo
backend because GitHub enforces a 2-GiB asset limit.

### Ordinary temporary build

The public API can create a `build-JOB_ID` GitHub Release only when the tarball
is below 1.9 GiB. A scheduled workflow runs every six hours and deletes
`build-*` releases older than two days, so effective retention is roughly
48--54 hours.

Important current limitation:

- a public temporary build above 1.9 GiB completes all expensive package work
  and then fails because Zenodo is not allowed for temporary output;
- the 9.35-Gbp benchmark produced a 2.31-GB tarball, so the same assembly would
  currently fail as an ordinary Web build.

Current scope decision:

- no pre-build rejection heuristic and no R2-backed large temporary-package
  store are planned in this round. The existing limitation remains explicit;
  a user build is never silently converted into permanent publication.

### Curated permanent build

This path is internal; the public Worker does not forward `publish_to_index`.
Small packages use permanent GitHub Releases, large packages use Zenodo, and a
second dispatch updates the gh-pages package index with storage metadata and
provenance.

Open improvements:

- reconcile cases where storage succeeds but index update fails.

The audit added exact filename, size, and SHA-256 checks before reusing an
existing release asset. A mismatch preserves the existing release and stops
the index update, so newly built provenance cannot describe different bytes.

### Benchmark build

A no-publish benchmark runs the complete build and archive-validation path,
then deletes the tarball and uploads only a small report artifact. Benchmark
reports are retained for 90 days.

Open improvements:

- add an explicit campaign pause flag checked before every dispatch; cancelling
  a serial matrix currently has a race at job boundaries;
- set the final metrics stage to `complete` or `cleanup`;
- record every measured stage directly instead of reconstructing validation
  time from GitHub timestamps.

## 13. Status and progress reporting

`GET /api/status/JOB_ID` first checks for a temporary GitHub Release. Until one
exists, the Worker searches recent repository-dispatch runs and fetches job
steps to reconstruct queue, source resolution/download, FASTA inspection or
streaming conversion, metadata generation, forge, archive compression,
archive validation, and release status.

Purpose:

- give users a stable project-domain endpoint rather than exposing GitHub API
  details or a workers.dev URL.

The audit makes completed failed, cancelled, and timed-out runs terminal even
without a failure-marker Release. A successful completed run whose temporary
artifact has expired reports that expiry. Success requires a published,
nonempty BSgenome tarball asset.

Known improvements:

- persist `job_id -> run_id/status` rather than scanning up to 300 workflow runs
  on every poll;
- return recorded CPU/transfer diagnostics through a durable status store if
  users eventually need completed-run telemetry beyond GitHub step wall time.

## Benchmark baseline before fast inspection

The controlled no-publish rerun for `GCA_963921465.1` used workflow run
`32555275665` and produced the following baseline:

| Stage | Elapsed |
|---|---:|
| NCBI download | 5 min 24 s |
| Exhaustive FASTA validation | 13 min 13 s |
| Header/statistics scan | 2 s |
| FASTA to 2bit | 1 min 00 s |
| Forge | 14 s |
| R CMD build | 1 min 48 s |
| Archive validation | 29 s |
| Workflow start to tarball | 21 min 41 s |
| Complete GitHub job | 22 min 52 s |

The tarball was 2,309,565,536 bytes, was not published to GitHub Releases,
Zenodo, or the permanent index, and was deleted after its benchmark report was
finalized.

## Benchmark result after fast inspection

The controlled no-publish rerun used the same accession and merged production
workflow (`80a3333`, run `32561399985`). It completed successfully:

| Stage | Before | After | Change |
|---|---:|---:|---:|
| NCBI download | 5 min 24 s | 4 min 48 s | -36 s |
| FASTA validation and statistics | 13 min 15 s | 4 s | -13 min 11 s |
| FASTA to 2bit | 1 min 00 s | 1 min 04 s | +4 s |
| Forge | 14 s | 11 s | -3 s |
| R CMD build | 1 min 48 s | 1 min 34 s | -14 s |
| Archive validation | 29 s | 26 s | -3 s |
| Workflow start to tarball | 21 min 41 s | 7 min 42 s | -13 min 59 s |
| Complete GitHub job | 22 min 52 s | 8 min 44 s | -14 min 08 s |

The core-build time fell by 64.5% and the complete job time by 61.8%. FASTA
inspection reported 1,672 records in a 9,468,495,736-byte uncompressed FASTA
and explicitly recorded that exhaustive validation was disabled. The
2,309,565,046-byte tarball passed archive validation and was then deleted. All
GitHub Release, Zenodo, and permanent-index publication steps were skipped; the
only retained artifact was the 3,188-byte benchmark report.

## Benchmark result with fine-grained metrics

Run
[`32619294902`](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32619294902)
repeated the same 9.35-Gbp `GCA_963921465.1` no-publish build on workflow
`2f4bba05`. It succeeded in 4 min 57 s, did not enter the NCBI Datasets
fallback, did not publish a package, and removed its tarball after validation.

The NCBI stream took 121.768 s wall time: Python decompression/inspection used
55.044 CPU seconds and `faToTwoBit` used 63.931 CPU seconds. Package forge took
12 s, `R CMD build` took 106 s, archive validation took 24 s, and workflow start
to validated tarball took 244 s. The complete report records the original
compressed MD5, all byte counts, stage resource peaks, and successful cleanup.

Compared with the earlier 4 min 23 s streaming run, this run was 34 s slower;
27 s of the difference was package compression and 13 s was acquisition plus
conversion, partly offset by a 1-s faster forge. Identical source MD5 and byte
counts, a 14-byte tarball-size difference, one transfer attempt, and no fallback
support treating the difference as normal hosted-runner/transfer variation.

## Decision backlog

### Adopted

- Remove circular-sequence detection and fix seeds to `character(0)`.
- Remove exhaustive Python FASTA validation.
- Use prefix-sampled validation only for URL/upload input.
- Merge FASTA inspection and statistics into one workflow stage.
- Keep archive validation.
- Read each package archive once while hashing and validating it through `tee`.
- Stream Ensembl, custom URL, and uploaded FASTA directly to inspection and
  `faToTwoBit`, without materializing `genome.fa`.
- Preserve package compression ratio rather than trading package size for speed.
- Expose resolver, conversion, forge, compression, validation, and release as
  separate user-visible progress stages.
- Keep approximately two-day cleanup for ordinary temporary downloads.
- Never silently publish a user build to the permanent index.

### Rejected performance proposals

- Alternate gzip implementations, levels, or packaging profiles.
- Native or parallel decompression in the acquisition stream.
- Hardlink/reflink substitution for BSgenomeForge's copy behavior.
- Hashing and validation during archive creation.
- NCBI dehydrated packages followed by `datasets rehydrate`; this adds an
  unnecessary acquisition lifecycle and does not improve the primary FTP
  stream or solve converter memory.
- Sharded `faToTwoBit` conversion plus a custom lossless 2bit merger; the added
  binary-format correctness and maintenance surface is not justified for the
  current product.
- Adding an NCBI API key as a response to the 87-94-Gbp failures. Those
  failures were converter memory, runner disk, and transfer integrity failures,
  not request-rate limiting; the primary Genomes FTP stream does not use the
  Datasets API key.

### Needs a product decision

- Decide how strict custom FASTA validation must be.
- Decide whether public builds need authentication, quotas, or challenge-based
  abuse protection.

### Engineering work without a product-policy decision

- Durable status storage beyond the recent-workflow lookup window.
- Narrow forge fallback.
- Preflight disk estimation and upstream checksum handling.
- Explicit benchmark pause control and improved metrics completeness.
