# Large-genome build benchmarks

This document records observed autoBSgenome builds of multi-gigabase genome
assemblies. It does not infer a genome-size or assembly-contiguity limit from
the historical runs because those runs used different workflow revisions.

## Historical observations

| Organism | NCBI accession | NCBI total length | NCBI scaffolds | Scaffold N50 | Observed result | Run |
|---|---|---:|---:|---:|---|---|
| *Hordeum vulgare* cv. Du Li Huang | `GCA_903970715.1` | 4.68 Gbp | 47,929 | 658,974,642 bp | Built in 3 min 42 s | [24615911380](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24615911380) |
| *Triticum timopheevii* | `GCA_963921465.1` | 9.35 Gbp | 1,670 | 671,191,297 bp | Built in 7 min 53 s | [24634536259](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24634536259) |
| *Triticum aestivum* cv. Chinese Spring | `GCA_018294505.1` | 14.57 Gbp | 91,588 | 713,360,525 bp | Built in 12 min 05 s | [24637137434](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24637137434) |
| *Pinus taeda* | `GCA_000404065.3` | 22.10 Gbp | 1,760,464 | 107,038 bp | Built in 34 min 18 s | [24637880719](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24637880719) |
| *Ambystoma mexicanum* | `GCA_002915635.3` | 28.21 Gbp | 27,157 | 1,205,706,733 bp | Failed after 29 min 23 s | [24638585963](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24638585963) |
| *Neoceratodus forsteri* | `GCA_016271365.2` | 34.56 Gbp | 46 | 1,485,207,024 bp | Built in 35 min 20 s | [24644421308](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24644421308) |

Assembly size is NCBI `total_sequence_length`. The sequence-count column is
NCBI `number_of_scaffolds`; the FASTA record count is recorded separately by
the workflow because the two values are not guaranteed to be identical.

### Why the historical rows are not a controlled benchmark

The *P. taeda*, *A. mexicanum*, and *N. forsteri* runs used commits
`097cd303`, `b0844840`, and `d8816b4f`, respectively. Disk cleanup and external
GNU tar support were added between those revisions. Their elapsed times remain
useful observations, but cross-row causal comparisons are not valid.

The retained GitHub check annotation for the historical *A. mexicanum* run is
`System.IO.IOException: No space left on device`. The earlier OOM and
contiguity explanations were inferences from incomplete logs and are withdrawn.
The current workflow must be retested before discussing the assembly's outcome.

## Controlled 2026 campaign

The current campaign contains 20 NCBI assemblies from 21.93 to 94.26 Gbp. Its
versioned source of truth is
[`large-genomes-2026.json`](../.github/benchmarks/large-genomes-2026.json), and
the sequential orchestrator is
[`large-genome-benchmark-2026.yml`](../.github/workflows/large-genome-benchmark-2026.yml).
The manual `from_order` and `through_order` inputs can run an exact contiguous
subset without rebuilding completed campaign entries.

All campaign builds:

- use the same workflow commit and pinned builder-image digest;
- download the exact NCBI accession in the manifest;
- run once, sequentially, without automatic build retries;
- use 60 minutes as the core-build SLA and 180 minutes as the job hard limit;
- distinguish tarball completion, publication completion, and workflow completion;
- retain stage timings, actual FASTA record count, peak disk, peak memory,
  archive integrity, checksum, and the exact failure stage.

An exact existing `NCBI + accession` package is rebuilt for measurement but is
not uploaded or re-indexed. The two known existing NCBI packages, *Pinus
taeda* `GCA_000404065.3` and *Neoceratodus forsteri* `GCA_016271365.2`, also
carry an explicit no-publication policy in the manifest. A package with the
same accession from Ensembl has a distinct provider identity and does not
suppress publication of the NCBI package.

The campaign result artifact will contain JSON, CSV, and Markdown tables. No
causal statement about total length or contiguity will be added until all 20
first-run results have been collected.

### Initial workflow validation (2026-08-23)

The first three campaign entries completed successfully in the same sequential
[campaign run](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/32625225234).
Each NCBI download used one direct FTP stream into `faToTwoBit -long`, and each
archive passed the single-stream archive validation.

| Organism | Accession | FASTA records | Stream to 2bit | Compress | Validate | Core build | Tarball | Publication |
|---|---|---:|---:|---:|---:|---:|---:|---|
| *Pleurodeles waltl* | `GCA_054660815.1` | 2,679 | 4 min 21 s | 3 min 49 s | 53 s | 8 min 34 s | 5.26 GB | [Zenodo 22066005](https://zenodo.org/records/22066005), 9 min 31 s |
| *Pinus taeda* | `GCA_000404065.3` | 1,760,464 | 3 min 16 s | 3 min 31 s | 41 s | 7 min 23 s | 5.53 GB | Explicitly skipped; existing record unchanged |
| *Pinus radiata* | `GCA_050662955.1` | 305,167 | 4 min 51 s | 4 min 38 s | 1 min 02 s | 9 min 56 s | 5.94 GB | [Zenodo 22066355](https://zenodo.org/records/22066355), 8 min 40 s |

`Core build` is the measured workflow start through validated package archive;
publication is reported separately. The benchmark-only *P. taeda* tarball was
deleted after validation and did not create a release, Zenodo record, or index
entry. Its 7 min 23 s result replaces neither the historical observation nor
the existing package; it is a controlled measurement of the current workflow.

### Completed campaign results (2026-08-23)

The controlled campaign produced and validated a package for 18 of 20
assemblies. `FASTA records` is the count observed in the streamed source; it is
kept separate from NCBI's scaffold count because the values are not identical
for every accession. Successful elapsed times run from workflow start through
archive validation. Failed elapsed times run through terminal job failure.

| # | Organism | Accession | Level | Size (Gbp) | NCBI scaffolds | FASTA records | Scaffold N50 (bp) | Core build | Elapsed |
|---:|---|---|---|---:|---:|---:|---:|---|---:|
| 1 | *Pleurodeles waltl* | `GCA_054660815.1` | Contig | 21.93 | 2,679 | 2,679 | 60,529,522 | success | 8 min 34 s |
| 2 | *Pinus taeda* | `GCA_000404065.3` | Scaffold | 22.10 | 1,760,464 | 1,760,464 | 107,038 | success | 7 min 23 s |
| 3 | *Pinus radiata* | `GCA_050662955.1` | Chromosome | 22.41 | 305,167 | 305,167 | 221,616 | success | 9 min 56 s |
| 4 | *Calotriton arnoldi* | `GCA_963921515.1` | Scaffold | 22.89 | 47,257 | 47,257 | 1,649,920 | success | 9 min 57 s |
| 5 | *Lissotriton helveticus* | `GCA_964261635.2` | Chromosome | 23.17 | 447 | 448 | 2,132,484,007 | success | 10 min 15 s |
| 6 | *Lissotriton vulgaris* | `GCA_964263255.2` | Chromosome | 24.23 | 15,248 | 15,249 | 1,925,992,481 | success | 9 min 57 s |
| 7 | *Pinus tabuliformis* | `GCA_031772625.1` | Chromosome | 24.41 | 17 | 17 | 1,392,452,741 | success | 10 min 56 s |
| 8 | *Picea engelmannii* | `GCA_009831015.1` | Scaffold | 24.94 | 946,236 | 946,236 | 403,791 | success | 10 min 10 s |
| 9 | *Sequoia sempervirens* | `GCA_007258455.2` | Scaffold | 26.55 | 393,370 | 393,407 | 45,116,641 | success | 11 min 31 s |
| 10 | *Picea glauca* | `GCA_000966675.3` | Scaffold | 26.57 | 2,445,336 | 2,445,336 | 161,389 | success | 11 min 40 s |
| 11 | *Pinus lambertiana* | `GCA_001447015.2` | Scaffold | 27.60 | 4,253,074 | 4,253,097 | 292,685 | success | 12 min 55 s |
| 12 | *Pinus albicaulis* | `GCA_034641835.3` | Chromosome | 27.61 | 34,178 | 34,178 | 1,634,761,663 | success | 14 min 21 s |
| 13 | *Ambystoma mexicanum* | `GCA_002915635.3` | Chromosome | 28.21 | 27,157 | 27,157 | 1,205,706,733 | success | 12 min 19 s |
| 14 | *Ambystoma opacum* | `GCA_047292645.1` | Scaffold | 29.02 | 9,389,658 | 9,389,658 | 55,462,223 | success | 9 min 35 s |
| 15 | *Neoceratodus forsteri* | `GCA_016271365.2` | Chromosome | 34.56 | 46 | 46 | 1,485,207,024 | success | 16 min 52 s |
| 16 | *Euphausia superba* | `GCA_051903835.1` | Contig | 38.15 | 1,011,214 | 1,011,214 | 48,277 | success | 18 min 18 s |
| 17 | *Protopterus annectens* | `GCA_040939525.1` | Chromosome | 40.52 | 7,124 | 7,125 | 1,950,821,829 | success | 18 min 56 s |
| 18 | *Paris polyphylla* var. *yunnanensis* | `GCA_060040675.1` | Scaffold | 48.15 | 51 | 51 | 1,000,551,444 | success | 24 min 37 s |
| 19 | *Lepidosiren paradoxa* | `GCA_040581445.1` | Chromosome | 87.22 | 15,903 | — | 1,992,257,274 | failed: converter memory, then fallback transport | 49 min 12 s |
| 20 | *Viscum album* | `GCA_963277665.1` | Chromosome | 94.26 | 5,096 | — | 2,134,690,998 | failed: converter memory, then fallback disk | 1 h 10 min 16 s |

The core build and publication outcomes are independent. *Sequoia
sempervirens*, *Picea glauca*, and *Pinus lambertiana* produced validated
packages but their first Zenodo publication attempts failed. *Pinus taeda* and
*Neoceratodus forsteri* were intentionally not republished because the exact
NCBI accessions already existed. The remaining 13 successful core builds were
published.

## Known format and storage thresholds

| Boundary | Current behavior |
|---|---|
| GitHub Release asset near 1.9 GiB | Publish the permanent package through Zenodo |
| Large FASTA / 2bit 32-bit index | Use `faToTwoBit -long` |
| R internal tar near 8 GB | Use external GNU tar through `R_BUILD_TAR=tar` |

These are implementation thresholds, not claims about which genome assemblies
will complete on the hosted runner.
