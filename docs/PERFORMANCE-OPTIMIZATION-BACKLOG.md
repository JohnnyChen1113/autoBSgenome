# Build performance optimization backlog

Last updated: 2026-08-23

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

## Implemented and measured: NCBI FASTA streaming to 2bit

The NCBI fast path resolves the accession's official Genomes FTP
`*_genomic.fna.gz` file and its published MD5, then processes one data stream:

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

Production validation used two no-publish builds. The 12-Mbp
`GCF_000146045.2` integration run
[`32586450061`](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32586450061)
completed the FTP stream, package forge, archive validation, and benchmark
cleanup in 48 seconds. The 9.35-Gbp comparison run
[`32586564995`](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32586564995)
completed successfully without entering the Datasets fallback:

| Metric | Previous run `32561399985` | Streaming run `32586564995` | Change |
|---|---:|---:|---:|
| NCBI acquisition + inspection + 2bit | 356 s | 110 s | -69% |
| Forge | 11 s | 13 s | +2 s |
| R CMD build | 94 s | 79 s | -16% |
| Archive validation | 26 s | 21 s | -19% |
| Workflow start to tarball | 462 s | 207 s | -55% |
| Complete GitHub job | 524 s | 263 s | -50% |

The large streaming run verified NCBI compressed MD5
`e411fb3288a0b67cf328be438fe884c7`, read 2,801,159,935 compressed bytes and
9,468,495,736 FASTA bytes, counted 1,672 sequences, and produced a
2,543,657,067-byte 2bit file. Archive validation passed. All publication steps
were skipped and the ephemeral benchmark tarball was removed.

## Implemented: streaming Ensembl, URL, and upload inputs to 2bit

The three non-NCBI acquisition paths now use the same bounded-memory public
interface as the NCBI fast path. The HTTP response is inspected and passed to
`faToTwoBit stdin` as it arrives; gzip is detected from stream magic bytes and
plain FASTA remains supported. These paths no longer materialize a compressed
download and an uncompressed `genome.fa`, then scan and read that FASTA again.

Custom URL and upload inputs retain prefix-sampled nucleotide validation.
Ensembl input retains official-source metadata inspection. Transfer retries
restart the complete stream, a successfully consumed upload is still deleted
best-effort, and input bytes, MD5, compression mode, wall time, Python CPU,
converter CPU, attempt count, FASTA size, sequence count, and 2bit size are
recorded.

Because a streamed custom source may not advertise its uncompressed size, a
specific UCSC 32-bit index-overflow failure requests one clean retry with
`faToTwoBit -long`. Small inputs retain the ordinary version-0 2bit format;
`-long` is not enabled unconditionally because the
[UCSC implementation](https://github.com/ucscGenomeBrowser/kent/blob/master/src/utils/faToTwoBit/faToTwoBit.c#L21-L22)
documents that format as incompatible with older readers.

Production validation covered every new path with no-publish builds:

| Source | Run | Input mode | Complete job | Result |
|---|---:|---|---:|---|
| Ensembl | [`32619146651`](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32619146651) | gzip | 46 s | success |
| URL | [`32619145392`](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32619145392) | gzip | 45 s | success |
| Upload | [`32619944918`](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32619944918) | plain | 41 s | success |

Each run used one streaming attempt, completed package forge and archive
validation, skipped publication, and removed its benchmark tarball. The upload
test additionally verified prefix-sampled validation and confirmed that the
consumed R2 object returned HTTP 404 after workflow cleanup.

## Not adopted: parallel package compression

Package size is a product constraint, not only a storage detail. The project
will not trade compression ratio for a shorter `R CMD build`, because keeping
tarballs below the GitHub 2-GiB asset limit whenever possible is more valuable
than saving compression time. The current package-building compression path is
therefore retained.

Do not replace `R CMD build` with direct tar assembly until archive contents and
install/load behavior have been shown equivalent on both small and very large
packages.

## Rejected: alternate package compressors and compression tuning

The project will not benchmark or substitute `libdeflate-gzip`, single-threaded
`pigz`, or alternate gzip levels in the package-build path. Even a conditional
"no size regression" compressor selection adds a second packaging profile and
reproducibility surface. Keep the current `R CMD build` compression path.

## Rejected: alternate or parallel streaming decompression

The project will not replace the Python gzip implementation in the acquisition
pipeline with native, `libdeflate`, or parallel decompression. The new CPU
metrics remain useful for diagnosis, but decompressor substitution is not an
accepted optimization even if a future benchmark shows available CPU headroom.

## Rejected: forge hardlinks or reflinks

The project will not alter BSgenomeForge's normal copy semantics with hardlinks
or filesystem-specific reflinks. Forge was only 13 seconds in the measured
9.35-Gbp build, so the potential wall-time saving does not justify introducing
filesystem-dependent package assembly behavior.

## Implemented: checksum and archive validation in one pass

The archive is now read once. `tee` sends the same compressed byte stream to
SHA-256 and `tar -tzf -`; validation still requires `DESCRIPTION` and
`inst/extdata/single_sequences.2bit`. A truncated stream or either consumer
failing rejects the archive.

## Rejected: validation during archive creation

Archive hashing and validation will remain a post-build read. Intercepting the
tar/gzip stream produced by `R CMD build`, or replacing part of `R CMD build`
with direct archive assembly, is rejected because it couples validation to R's
packaging internals and raises package-equivalence risk. The accepted `tee`
implementation is the optimization boundary.

## Not adopted: short-lived 2bit cache

A multi-gigabyte 2bit cache would add storage lifecycle and cache-validity
complexity. The project will not introduce this cache. Deliberate rebuilds and
benchmarks continue to execute the real acquisition and conversion path.

## Implemented: finer timing instrumentation and visible progress

The workflow now records NCBI resolver and streaming wall times, Python
decompression/inspection CPU, `faToTwoBit` child-process CPU, seed generation,
forge, package compression, archive validation, and storage selection. Existing
coarser timing keys remain for report compatibility.

The status API and Build page expose observable workflow stages separately:
source resolution/download, FASTA inspection or streaming conversion, metadata
generation, package forge, archive compression, archive validation, and upload.
Operations intentionally executed in one streaming pipeline remain one live
step rather than being serialized for display.

## Measured: 9.35-Gbp rerun with fine-grained metrics

The controlled no-publish rerun of `GCA_963921465.1` used merged production
workflow `2f4bba05` and run
[`32619294902`](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32619294902).
It completed successfully in one NCBI FTP attempt, matched compressed MD5
`e411fb3288a0b67cf328be438fe884c7`, passed archive validation, skipped every
publication path, and removed the ephemeral tarball.

| Metric | Earlier streaming run `32586564995` | Fine-metrics run `32619294902` | Change |
|---|---:|---:|---:|
| NCBI acquisition + inspection + 2bit | 110 s | 123 s | +13 s |
| Forge | 13 s | 12 s | -1 s |
| R CMD build | 79 s | 106 s | +27 s |
| Archive validation | 21 s | 24 s | +3 s |
| Workflow start to tarball | 207 s | 244 s | +37 s |
| Complete GitHub job | 263 s | 297 s | +34 s |

The stream itself took 121.768 seconds. Python decompression and inspection
used 55.044 CPU seconds, while `faToTwoBit` used 63.931 CPU seconds. Their
combined 118.975 CPU seconds equal 97.7% of stream wall time, showing that the
pipeline spends substantial time in the accepted Python-plus-converter path
rather than merely waiting on the network. This is diagnostic evidence only:
native or parallel decompression remains rejected.

The run read 2,801,159,935 compressed bytes and 9,468,495,736 FASTA bytes,
produced a 2,543,657,067-byte 2bit file, and created a 2,309,565,522-byte
tarball. These values and the MD5 match the earlier streaming run; the tarball
differed by only 14 bytes. The 34-second job difference is concentrated in
compression and stream wall time and should be treated as hosted-runner and
transfer variability, not as evidence of an added materialization pass.

## Diagnosed: the monolithic faToTwoBit memory ceiling

The 2026 large-genome campaign diagnosed a hosted-runner memory failure mode,
not a fragmentation or NCBI rate-limit ceiling. It does not establish a fixed
genome-size cutoff. The largest completed build, 48.15-Gbp
`GCA_060040675.1`, succeeded with peak process RSS of 15.46 GB, already close
to the approximately 16-GB runner limit. The 87.22-Gbp `GCA_040581445.1` and
94.26-Gbp `GCA_963277665.1` streams both lost their downstream converter when
memory reached that limit. In UCSC's implementation, `faToTwoBit` constructs
the packed representation of every sequence before it writes the file;
`-long` changes index-offset width but does not bound memory.

Implemented follow-up:

- a converter that exits or is killed while the stream is being written is now
  reported by its real exit status or signal instead of the upstream
  `Broken pipe` symptom;
- Linux cgroup `oom_kill` counters are included when they confirm an OOM kill;
- converter-process failure uses a distinct exit code and stops immediately,
  because repeating the download or switching acquisition paths cannot repair
  the same converter failure;
- NCBI Datasets is fixed at 18.36.0 and fallback progress bars are disabled.

### Rejected: sharded UCSC conversion and lossless merge

The evaluated design would cap each `faToTwoBit` invocation at a bounded shard,
for example 4-6 Gbp of complete FASTA records, and introduce a new merger that
writes a version-1 header and 64-bit index around the already-packed sequence
records. This could bound converter memory while retaining UCSC's record
encoding.

The proposal was rejected on 2026-08-23. It adds a custom binary-format merger,
substantial correctness testing, and long-term maintenance solely to extend an
extreme-genome boundary that is not required by the current product. Do not
implement it. The workflow will retain the standard monolithic UCSC
`faToTwoBit` conversion and report its failure clearly when a build exceeds the
hosted runner's available memory.

The rejected design would also require the shard files and final 2bit to coexist
during the merge, approximately doubling 2bit disk demand. Package forge and
compression would still need a separate disk-budget audit at this scale.

### Other converter options rejected or not adopted

- A clean-room, disk-spooled Rust version-1 2bit writer can be fully streaming
  and memory-bounded, but has an even larger correctness and maintenance
  surface. It is not planned.
- The MIT-licensed Rust `twobit` crate is not a drop-in solution: its current
  writer emits version 0, stores masking metadata from a first FASTA scan, and
  requires seekable input for later sequence reads.
- BSgenome's per-sequence RDS or RAZip FASTA storage modes avoid one monolithic
  2bit, but would change package layout, size, and runtime behavior; millions of
  per-sequence files make RDS unsuitable for fragmented assemblies.
- Splitting one assembly into multiple BSgenome packages is rejected because
  it changes the user-visible genome identity and installation model.

### Rejected: NCBI dehydrated then rehydrate

NCBI's documented path for data packages over 15 GB first downloads a small
dehydrated ZIP containing metadata and the locations listed in `fetch.txt`,
then unzips it and runs `datasets rehydrate` to retrieve the actual files.
This was rejected on 2026-08-23. It adds an extra metadata-package,
unpack, and rehydrate lifecycle without improving the primary FTP stream or
solving the observed `faToTwoBit` memory ceiling. Do not implement it. The
current direct NCBI Datasets ZIP remains the compatibility fallback when the
primary Genomes FTP stream cannot be used.

An NCBI API key is intentionally not part of this work. It raises request-rate
limits for Datasets API calls, but the observed failures were converter memory,
runner disk, and long-transfer integrity failures rather than HTTP 429 rate
limiting. The direct Genomes FTP stream does not use a Datasets API key.

## Not currently justified: warm self-hosted runners

A warm runner could avoid roughly 30 seconds of container initialization, but
it adds security isolation, maintenance, scaling, and reproducibility costs.
Reconsider only if runner initialization becomes a dominant measured cost.
