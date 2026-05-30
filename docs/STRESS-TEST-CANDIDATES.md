# Large-genome stress-test roster

Snapshot of all genomes touched (or queued) by the large-genome pressure-test
campaign, ordered by total raw size. The goal is to map the contiguity ceiling
empirically — the binding constraint on free-tier GitHub Actions runners is
per-sequence overhead in R during `forgeBSgenomeDataPkg`, not nucleotide
volume. See `LARGE-GENOME-BENCHMARKS.md` for run-level timing detail.

**Contiguity grade legend**
- ✅ Chromosome-level, few records — predicted safe regardless of size
- 🟡 Many scaffolds (~hundreds to low thousands) — borderline
- 🔴 Heavily fragmented (≳10,000 records) — at high OOM risk on free-tier
- ❓ Not yet fetched

## Roster

| Status | Organism | Assembly | Source | Raw size | Records | Contiguity | Result | Notes |
|---|---|---|---|---|---|---|---|---|
| ✅ done | *Hordeum vulgare* cv. DuLiHuang | `Hvulgare_cv_Du_Li_Huang_ZDM01467_BPGv2` | Ensembl Plants | 4.27 GB (NCBI reports; LARGE-GENOME-BENCHMARKS recorded 5.3 GB likely includes intermediate disk) | **627 scaffolds, 1,161 contigs** | 🟡 | Built 3:42 | 7 chromosomes; scaffold N50 = 612 Mb; barley pangenome BPGv2 line |
| ✅ done | *Triticum timopheevii* | `WRC_timopheevii_genome_with_organelles` | Ensembl Plants | 9.35 GB | **1,670 scaffolds, 2,304 contigs** | 🟡 | Built 7:53 | 14 chromosomes; scaffold N50 = 671 Mb; Zenodo backend |
| ⏳ queued | *Triticum dicoccoides* (wild emmer wheat) | `WEW_v2.1` (GCF_002162155.2) | NCBI | 10.68 GB | **148,296 scaffolds** (492,885 contigs) | 🔴 | Reset 2026-05-14, awaiting cron | Scaffold N50 = 747 Mb, but tail of 148k unplaced scaffolds. Status was `skip_oversized` from pre-toolchain era; now re-queued for true OOM/contiguity test |
| ✅ done | *Triticum aestivum* (bread wheat) | `IWGSC_RefSeq_v2.1` | Ensembl Plants | 14.57 GB | ~21 scaffolds | ✅ | Built 12:05 | Zenodo; chromosome-level published as 21 scaffolds |
| ✅ done | *Pinus taeda* (loblolly pine) | `Ptaeda2.0` | NCBI / Ensembl | 22.10 GB | several thousand scaffolds | 🟡 | Built 34:18 | Zenodo + `-long` 2bit. Triggered the 4 GB 2bit-index limit discovery |
| ❌ failed | *Ambystoma mexicanum* (axolotl) | `AmbMex60DD` | NCBI | 28.21 GB | **27,157 contigs** | 🔴 | R forge OOM | First demonstration that contig count, not base count, is the binding ceiling |
| ✅ done | *Neoceratodus forsteri* (Australian lungfish) | `neoFor_v3.1` | NCBI | 34.56 GB | **46 chromosome-level seq** | ✅ | Built 35:20, peak RSS 708 MB | Decisive proof of the contiguity hypothesis: 23% larger than axolotl in bases yet ≳20× less peak R memory because 591× fewer records |

## Candidates not yet attempted — confirmed available on NCBI

Ordered by predicted information value for the contiguity-ceiling hypothesis.
Stats fetched from NCBI Datasets API 2026-05-14.

| Priority | Organism | Assembly | Size | Records | Contiguity | What this test would settle |
|---|---|---|---|---|---|---|
| **P1** | *Protopterus annectens* (African lungfish) | **PAN1.0** (27 chromosomes) | **40.05 GB** | **12,667 scaffolds**, 74,227 contigs | 🟡-🔴 | Lies on the contig axis **between N. forsteri (46, ✅) and axolotl (27,157, ❌)**. Either outcome tightens the OOM threshold. Also pushes the size axis +16% above current 34.56 GB record. Top priority. |
| **P1-alt** | *Protopterus annectens* (alternative assembly) | `ASM4093952v1` (27 chromosomes) | 40.52 GB | **7,124 scaffolds**, 31,562 contigs | 🟡 | Slightly cleaner than PAN1.0; if PAN1.0 fails the alt would test whether ~7K scaffolds still passes |
| **P2** | *Pinus lambertiana* (sugar pine) | recent NCBI | ~31 GB | TBD | TBD | Conifer scaling above *P. taeda* 22 GB; fetch stats before scheduling |
| **P3** | *Picea abies* (Norway spruce) | recent NCBI | ~20 GB | TBD | TBD | Fills in conifer curve; lower information value than P1 |
| **P4** | *Pseudotsuga menziesii* (Douglas fir) | recent NCBI | ~15-17 GB | TBD | TBD | Duplicates P3 data point band |
| **P5** | *Allium cepa* (onion) | recent NCBI | ~16 GB | TBD | TBD | Monocot at bread-wheat band |

## Stretch goal: *Lepidosiren paradoxa* (South American lungfish)

NCBI 2024-release `ASM4058144v1`: **87.22 GB chromosome-level**, 15,903
scaffolds. This is **2.5× larger than current ceiling** and approaches the
GHA hosted runner's ~88 GB disk envelope — likely cannot fit raw FASTA +
2bit + package staging concurrently even with all current cleanup layers.
Realistic only on self-hosted runner. Worth noting in the paper as
"identified but deferred" rather than queuing for free-tier attempt.

## Why *Paris japonica* and large *Fritillaria* are off the table

These were originally listed as "upper-bound candidates" in
`LARGE-GENOME-BENCHMARKS.md`, but a closer look at NCBI in 2026-05 reveals
**they are biology problems, not infrastructure problems**.

| Species | C-value (flow cytometry) | NCBI assemblies | Assembled size | Why off the table |
|---|---|---|---|---|
| *Paris japonica* | ~149 Gbp (Pellicer et al. 2010) | **0** | — | No reference assembly exists. The genome size estimate is from Feulgen densitometry; no one has sequenced and assembled it. There is nothing to feed into autoBSgenome. |
| *Fritillaria* (genus) | 30-150 Gbp depending on species | **1** (*F. borealis* `ASM436807v1`) | **143 MB**, 142,328 scaffolds | The only genus member with any NCBI assembly is a **partial draft of ~0.1% of the predicted genome size**, fragmented into 142K short scaffolds. It would build (small size) but is biologically uninformative for BSgenome use. |

These two cases illustrate a useful framing point for the paper: the
practical ceiling on BSgenome construction is set by **what assemblies
actually exist**, not by what genome sizes are physically possible. The
universe of buildable references is bounded above by sequencing/assembly
state-of-the-art, not by autoBSgenome's runtime. The infrastructure has
headroom that the biology has not yet filled.

## Hard limits to keep in mind

| Limit | Threshold | Implication |
|---|---|---|
| GitHub Release single asset | 1.9 GiB | Tarballs above → Zenodo |
| UCSC 2bit default index | 4 GB output | FASTA > 12 GB → `faToTwoBit -long` |
| R internal `utils::tar()` | 8 GB tarball | → `R_BUILD_TAR=tar` (external GNU tar) |
| GHA hosted runner RAM | 16 GB | Binds **sequence-record count**, not base count |
| GHA hosted runner disk | ~88 GB usable | Bounds (raw FASTA + 2bit + package staging) concurrent |
| GHA per-job hard timeout | 6 h | Never actually approached; lungfish was 35 min |
| Zenodo per-record | 50 GB | Caps single-record artifact distribution |

## How to update this doc

When a new pressure test runs:
1. Move the row from "Candidates not yet attempted" to the main roster.
2. Fill in actual record count from NCBI Datasets API (`/genome/accession/.../dataset_report`).
3. Record outcome (built / failed / OOM) and timing.
4. If failed, append a "Failures encountered" entry in `LARGE-GENOME-BENCHMARKS.md` with run URL + step-level diagnosis.
5. Update `paper/draft-v4-outline.md` R4 table if the new data point materially shifts the contiguity story.

## Open questions

1. ~~Contiguity values for *H. vulgare* DuLiHuang and *T. timopheevii*~~
   **Resolved 2026-05-14** — fetched from NCBI Datasets API. Both are 🟡
   contiguity (627 and 1,670 scaffolds respectively). Available for plotting
   on F4 contig-count axis.
2. For each remaining `TBD` in the candidate list (P2–P5), fetch real
   record counts before dispatching, to avoid wasting runner time on
   assemblies we already know will OOM.
3. Once wild emmer wheat (Tdicoccoides WEW_v2.1) finishes its retry, this
   table gets its first **true 5th data point on the contig-count axis**
   — currently the contiguity figure rests on the lungfish vs axolotl
   contrast plus two bracketing points (DuLiHuang 627 scaf ✅, *T.
   timopheevii* 1,670 scaf ✅).

## Updated F4 dataset (post-2026-05-14 enrichment)

The figure can now plot the following confirmed (assembly size, sequence
record count, outcome) tuples:

| Organism | Size (GB) | Records | Outcome |
|---|---|---|---|
| *H. vulgare* cv. DuLiHuang | 4.27 | 627 | ✅ |
| *T. timopheevii* | 9.35 | 1,670 | ✅ |
| *T. aestivum* | 14.57 | ~21 | ✅ |
| *P. taeda* | 22.10 | several thousand (TBD exact) | ✅ |
| *A. mexicanum* | 28.21 | 27,157 | ❌ OOM |
| *N. forsteri* | 34.56 | 46 | ✅ (708 MB RSS) |
| *T. dicoccoides* | 10.68 | 148,296 | ⏳ in flight |
| *P. annectens* (PAN1.0) | 40.05 | 12,667 | scheduled P1 |

Once wild emmer wheat and *P. annectens* return, we have 8 data points
spanning two orders of magnitude on the contig-count axis — sufficient for
a clean Figure F4.
