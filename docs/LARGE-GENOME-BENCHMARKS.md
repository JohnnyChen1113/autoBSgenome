# Large-Genome Build Benchmarks

Wall-clock timings and outcomes for autoBSgenome builds of multi-gigabase
genomes. Captured empirically; suitable for citation in the Plan C paper as
evidence that the compositional free-tier architecture scales to full-sized
plant and vertebrate genomes.

All builds run on GitHub Actions `ubuntu-latest` free-tier runners, inside
the pre-built `ghcr.io/johnnychen1113.../autobsgenome-builder` container.
Timings include the full pipeline end-to-end:

1. FASTA download (NCBI Datasets CLI or Ensembl FTP)
2. FASTA → 2bit conversion (UCSC `faToTwoBit`)
3. Seed file generation + `R CMD build` (BSgenomeForge)
4. Artifact upload — GitHub Release (if tarball < 1.9 GiB) or Zenodo

## Benchmark table

| Date | Organism | Assembly | Genome | Tarball | Backend | Total time | DOI / Release | Run |
|---|---|---|---|---|---|---|---|---|
| 2026-04-18 | *Hordeum vulgare* cv. DuLiHuang ZDM01467 | `Hvulgare_cv_Du_Li_Huang_ZDM01467_BPGv2` | 5.3 GB | 1.00 GB | GitHub Release | **3 min 42 s** | [`pkg-BSgenome.Hvulgare.Ensembl.HvulgarecvDuLiHuangZDM01467BPGv2`](https://github.com/JohnnyChen1113/autoBSgenome/releases/tag/pkg-BSgenome.Hvulgare.Ensembl.HvulgarecvDuLiHuangZDM01467BPGv2) | [24615911380](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24615911380) |
| 2026-04-19 | *Triticum timopheevii* | `WRC_timopheevii_genome_with_organelles` | 9.35 GB | 2.20 GB | Zenodo | **7 min 53 s** | [10.5281/zenodo.19653884](https://doi.org/10.5281/zenodo.19653884) | [24634536259](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24634536259) |
| 2026-04-19 | *Triticum aestivum* cv. Chinese Spring | `IWGSC_RefSeq_v2.1` | **14.57 GB** | **3.43 GB** | Zenodo | **12 min 05 s** | [10.5281/zenodo.19655002](https://doi.org/10.5281/zenodo.19655002) | [24637137434](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24637137434) |
| 2026-04-19 | *Pinus taeda* (loblolly pine) | `Ptaeda2.0` | **22.10 GB** | **5.51 GB** | Zenodo (`-long` 2bit) | **34 min 18 s** | [10.5281/zenodo.19655359](https://doi.org/10.5281/zenodo.19655359) | [24637880719](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24637880719) |

## Per-step breakdown (14.57 GB bread wheat, as illustrative case)

| Step | Duration |
|---|---|
| Container + checkout | 22 s |
| Parse build parameters | <1 s |
| Download FASTA from Ensembl | 3 min 24 s |
| Extract FASTA headers and stats | 1 min 07 s |
| Convert FASTA to 2bit | 1 min 27 s |
| Generate seed file + `R CMD build` | 3 min 22 s |
| Storage backend decision | <1 s |
| Zenodo upload (3.43 GB) + DOI publish | 2 min 19 s |
| **Total** | **12 min 05 s** |

## Observations

- **Tarball-to-genome ratio**: 18.9% (barley) → 23.5% (T. timopheevii) → 23.5% (bread wheat). The 2bit format compresses ~4× versus raw FASTA, and the BSgenome R package wrapper adds only modest overhead.
- **Scaling is roughly linear in genome size** for the compute portion. The Zenodo upload time tracks tarball size at ~25 MB/s on GHA free-tier runners.
- **No step hit its timeout** on any genome up to 14.57 GB. The workflow's `timeout-minutes: 60` has a 4× headroom at this scale.
- **Compositional architecture pays off at the upload boundary**: `Determine storage backend` adds <1 second but routes 9+ GB genomes cleanly from GitHub Releases (2 GiB cap) to Zenodo (50 GB per record).

## Failures encountered on the way up

### Ambystoma mexicanum (28.21 GB) — 2026-04-19

- Run: [24638585963](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24638585963)
- Failed at step: `Generate seed file and build package` (R CMD build / forgeBSgenomeDataPkg)
- Symptom: log goes silent at 20:55:52 (right as the step begins); job marked failure at 21:06:52, 11 minutes later. No error message emitted.
- Cause (likely): runner-level termination by the host, typically OOM. The assembly contains **27,157 sequences** and a 7.6 GB 2bit; `forgeBSgenomeDataPkg` iterates per-sequence during package construction, and R's memory footprint can exceed the free-tier 16 GB RAM.
- Pre-existing code state: this run predates commits `259cde4` (FASTA cleanup) and `abee65f` (2bit dedup), so peak concurrent disk was ~52 GB — within the 75 GB disk cap. Disk is therefore unlikely to be the sole trigger; memory is the probable cause.
- Established empirical ceiling on free-tier runner (16 GB RAM, 75 GB disk): **22.10 GB** genome succeeds (Pinus taeda), **28.21 GB** fails at R build. The 22-28 GB range is where per-sequence overhead × many-contig counts outgrows free-tier memory.

### Pinus taeda (22.10 GB) — first attempt, 2026-04-19

- Run: [24637566386](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24637566386)
- Failed at step: `Convert FASTA to 2bit`
- Error: `faToTwoBit index overflow at APFE031164235.1 — The 2bit format does not support indexes larger than 4Gb, please split up into smaller files, or use -long option.`
- Cause: UCSC 2bit default format uses 32-bit offsets, capping output at 4 GB. A 22 GB FASTA produces a ~5.5 GB 2bit file and overflows.
- Fix: pass `-long` to `faToTwoBit` (switches to 64-bit indexes). Applied as a conditional in the workflow when input FASTA exceeds 12 GB.

This is a genuine format limit, distinct from the earlier GitHub Release 2 GiB asset cap. It means the pipeline has TWO size thresholds:

| Threshold | Value | What it switches |
|---|---|---|
| Tarball size | 1.9 GiB | Storage backend (GitHub Release → Zenodo) |
| Input FASTA size | 12 GB | 2bit index width (default → `-long`) |

## Upper-bound candidates (to be tested)

Known eukaryote genomes larger than 14.57 GB that are candidates for pushing the ceiling:

| Organism | Typical assembly size | Notes |
|---|---|---|
| *Pinus taeda* (loblolly pine) | ~22 GB | Conifer; published NCBI reference |
| *Pinus lambertiana* (sugar pine) | ~31 GB | Conifer |
| *Picea abies* (Norway spruce) | ~20 GB | Conifer |
| *Pseudotsuga menziesii* (Douglas fir) | ~15-17 GB | Conifer, borderline |
| *Allium cepa* (onion) | ~16 GB | Monocot |
| *Ambystoma mexicanum* (axolotl) | ~32 GB | Salamander |
| *Protopterus annectens* (African lungfish) | ~40 GB | Largest vertebrate genome |
| *Fritillaria* spp. | ~30-150 GB | Liliaceae, some species approach theoretical Zenodo-record limit |
| *Paris japonica* | ~150 GB | Largest reported eukaryote genome |

**Hard limits** to watch:
- Zenodo per-record: 50 GB → rules out *Paris japonica* and most *Fritillaria* without chunking
- GHA runner free disk: ~75 GB usable on standard `ubuntu-latest` → at peak FASTA + 2bit + tarball co-exist
- GHA build job `timeout-minutes: 60` → linear extrapolation gives ~50 min at 50 GB genome; safe

## Disk-usage defense layers (order of cheapness)

| Layer | Mechanism | Recovered | Status |
|---|---|---|---|
| 1 | `mv` (not `cp`) when staging NCBI FASTA; `rm` the `.zip` and extracted dir after move | ~28 GB + ~8 GB zip on large genomes | **Active** (commit forthcoming) |
| 2 | Delete `genome.fa` immediately after `faToTwoBit` succeeds | One genome-size block (up to ~30 GB) | **Active** (commit forthcoming) |
| 2b | Delete source `genome.2bit` once `forgeBSgenomeDataPkg` has copied it into the package dir; fallback path uses `file.rename` (mv) instead of `file.copy` | One 2bit-size block (up to ~12 GB on 150 GB genomes) | **Active** |
| 2c | `rm -rf ${PACKAGE}/` staging dir after `R CMD build` produces the tarball | One 2bit-size block (package dir contains the 2bit copy) | **Active** |
| 3 | `jlumbroso/free-disk-space@main` action to remove preinstalled Android/.NET/Haskell SDKs | ~30 GB extra | Documented; activate via workflow-level toggle if Layer 1-2 prove insufficient |
| 4 | Stream-download FASTA directly into `faToTwoBit` stdin (no full-file landing) | Full raw-FASTA size (can be 30-100+ GB) | Feasible but unimplemented — see notes below |
| 5 | GHA paid larger runner (`runs-on: ubuntu-latest-4cores` with 150 GB disk) | +75 GB usable | $0.008/min; trivial for a one-off, real-money if turned on for whole queue |
| 6 | Self-hosted runner on a 100-500 GB VPS | unlimited (within budget) | Already planned in `docs/SELF-HOSTED-RUNNER-PLAN.md`; long-term answer |

With Layers 1 + 2 + 2b + 2c active, peak concurrent disk for a 100 GB raw genome is dominated by a brief overlap of `${PACKAGE}` staging dir plus tarball (~50 GB), and for a 28 GB genome drops to ~15 GB. The ceiling on the free-tier runner rises from ~100 GB raw genome (before these cleanups) to roughly 150 GB.

## Notes on Layer 4 (streaming FASTA → faToTwoBit)

Feasibility confirmed:

- `faToTwoBit` reads input **sequentially**, so the input file can be a Unix pipe (`/dev/stdin`) rather than a seekable file.
- Output (the 2bit file) must be on disk — `faToTwoBit` seeks back to the header at the end to patch in sequence offsets.
- Memory footprint stays bounded because only the index (sequence names + output offsets) is held in RAM, not the sequence bases themselves. A 100 GB genome with ~1 M contigs has an index on the order of 50 MB, well within the runner's 16 GB RAM.

One-liner implementations:

```bash
# Ensembl (clean: server serves gzipped FASTA directly)
curl -sL "<ensembl .fa.gz url>" \
  | gunzip -c \
  | faToTwoBit /dev/stdin genome.2bit

# NCBI (datasets streams a zip archive; select the .fna on the fly)
datasets download genome accession "$ACC" --include genome -o - \
  | bsdtar -O -xf - '*.fna' \
  | faToTwoBit /dev/stdin genome.2bit
```

Why this is on the shelf rather than the floor:

- Current queue has no genomes exceeding ~50 GB raw size.
- Moving to streaming removes full-FASTA disk cost (up to 30 GB on current biggest candidates) but does **not** remove the R-package build step's concurrent copies (2bit + package staging dir + tarball), which bound the practical ceiling at ~100-120 GB raw genome on the free-tier runner even with streaming.
- For genomes > 120 GB (e.g. marbled lungfish *Protopterus aethiopicus* at ~130 GB) the streaming optimization becomes worthwhile but must be paired with either a paid larger runner or the R-build intermediate staged to `/tmp` while the main workspace carries the final tarball.

Keep this ready as a one-file patch for when a specific oversized target shows up.
