# autoBSgenome v4 — Outline (post-advisor pivot, 2026-05-14)

**Thesis type:** Tool + Resource paper (returns to Framing A territory)
**Target:** NAR Genomics & Bioinformatics (NARGAB)
**Mission statement:** **让天底下没有难构建的 BSgenome — no BSgenome is hard to build.**
**Split:** problem + tool 35% · resource coverage 45% · validation/benchmarks 20%

---

## What changed from v3 (Plan C)

After advisor discussion the **zero-cost / compositional-free-tier architectural** angle is dropped from the paper's selling points. v3 reframed the work as a methodology paper about sustainable bioinformatics infrastructure. We are pivoting back: the contribution is the **tool and the resource it generates**, full stop. Architecture details remain in Methods as implementation, with no "free tier", "zero cost", "sustainability", or "FAIR-S" rhetoric in abstract, introduction, or discussion.

| v3 (retired) had | v4 has |
|---|---|
| Architecture-as-thesis | Tool-and-resource thesis |
| "Tool longevity crisis" opening | BSgenome accessibility gap opening |
| Cost tables, failure-mode matrix, transferability | None of these — moved to GitHub docs if needed |
| "Sustainable" as missing FAIR axis | Removed |
| Reviewers asked "is this an engineering blog post?" | Reviewers see a clean tool + resource paper |

---

## Mission framing — "no BSgenome is hard to build"

The slogan does the same intellectual work that "让天下没有难做的生意" does for Alibaba: it names a constituency (researchers working on non-model organisms) and a frustration (BSgenome construction is technically gated), and promises that the tool removes the gate.

Concrete operationalization in the paper:
- **Who is gated today:** bench biologists studying any of the 3,500+ eukaryotic reference genomes outside the 33 currently packaged on Bioconductor.
- **What gates them:** command-line forgework with `BSgenomeForge`, seed-file authoring, 2bit conversion, circular-sequence detection, R CMD build/check — each step expects expertise most wet-lab researchers do not have.
- **What autoBSgenome removes:** every one of those steps is reduced to "paste accession → get installable package."

This frame is concrete, defensible, and does not require any architectural rhetoric.

---

## Abstract kernel (~200 words, draft)

> BSgenome data packages provide standardized access to reference genome sequences within R/Bioconductor and are required dependencies for 196 downstream packages spanning ChIP-seq, ATAC-seq, bisulfite sequencing, variant calling, and CRISPR design. Despite this central role, only 113 pre-built BSgenome packages exist on Bioconductor, covering 33 model organisms — a fraction of the 3,500+ eukaryotic reference genomes already available in public databases. Constructing a custom BSgenome package today requires command-line expertise, seed-file authoring, format conversions, and familiarity with `BSgenomeForge` internals — skills many bench biologists lack. We present **autoBSgenome**, a web service that converts any NCBI or Ensembl assembly accession into an installable, Bioconductor-compatible BSgenome package through a single accession-driven workflow. The user supplies only an accession; the system retrieves metadata, detects circular sequences, generates the seed file, builds the package, and returns an installable tarball. We benchmarked autoBSgenome across 33 genomes spanning fungi, plants, and vertebrates, with median build times of 44 s for small genomes (<100 MB) and 2–5 min for vertebrate-scale assemblies. In addition, we have systematically pre-built BSgenome packages for 3,553 eukaryotic reference genomes (NCBI 837 + Ensembl 2,716) and host them in a publicly accessible CRAN-like repository with browsable taxonomic indexing. By collapsing the construction workflow into a single accession entry, autoBSgenome makes BSgenome-dependent Bioconductor analyses available for the full breadth of sequenced eukaryotes.

Open question: should the abstract explicitly use the slogan "no BSgenome is hard to build" as a closing sentence, or is that too marketing-tone for NARGAB?

---

## Introduction (~900 words)

**1. BSgenome is a Bioconductor cornerstone, not a niche utility (~400 w)** ⭐ STRENGTHENED 2026-05-14

This section must do three jobs in sequence: (a) say *what* BSgenome is, (b) prove *what it does that a FASTA file cannot*, (c) quantify *how deeply the Bioconductor ecosystem rests on it*.

**1a. What BSgenome is** (~50 w)
- A versioned Bioconductor data package wrapping a reference genome assembly in UCSC 2bit format, exposed through an R API uniform across all assemblies.
- The standard substrate by which Bioconductor's coordinate-aware workflows (anything consuming `GRanges`) retrieve actual nucleotide content.
- Cite Pagès & Huber 2015 (Bioconductor reference); Kent et al. 2002 (2bit format).

**1b. Why a FASTA file is not sufficient — four capabilities BSgenome adds** (~180 w)
- **(i) Random-access retrieval via memory-mapped 2bit**: `getSeq(genome, GRanges("chr1:1e6-1e6+1000"))` returns sequence in O(1) without loading the rest of the genome. FASTA can be indexed (`.fai`) for similar access, but the returned object is a raw string lacking seqinfo metadata — every downstream Bioconductor function then has to be told the seqlengths and assembly separately.
- **(ii) Standardized metadata propagated through the type system**: `seqnames`, `seqlengths`, `isCircular`, `genome` are first-class slots that flow automatically into every `GRanges`/`VCF`/`SummarizedExperiment` derived from the genome. Circularity matters concretely — mitochondrial motif scanning wraps around the origin only if `isCircular=TRUE` is honored; a bare FASTA carries no such flag.
- **(iii) Versioned, citable, reproducibility-unit distribution**: `install.packages("BSgenome.Hsapiens.UCSC.hg38")` returns a byte-identical object on any machine that names the same version. Bioconductor's release cycle locks the package version into a globally reproducible dependency graph. A paper that says "we used `BSgenome.Hsapiens.UCSC.hg38` v1.4.5" is reproducible; a paper that says "we used hg38.fa from UCSC" is not, because the file at that URL can change without notice. **This is the singular capability FASTA structurally cannot match.**
- **(iv) Lazy-load memory profile at scale**: per-chromosome sequences load on first access only. Genome-wide motif scanning or CRISPR off-target search performs thousands of random queries against a constant ~50–200 MB RAM footprint; the FASTA-loaded-as-DNAStringSet equivalent commits the full genome (≥3 GB for human) up-front.

Concrete with-vs-without scenario (one paragraph): for a routine ChIP-seq peak motif analysis, the BSgenome workflow is `library(BSgenome.Hsapiens.UCSC.hg38); getSeq(., peaks)`. The FASTA-equivalent workflow requires downloading hg38.fa.gz (3 GB), decompressing, indexing with `samtools faidx`, shelling out from R or loading the full DNAStringSet, and tracking the assembly version manually because no R-level enforcement exists. The latter is technically possible and scientifically fragile.

**1c. Ecosystem entrenchment — and BSgenome's structurally distinct cost model** (~250 w)

Bioconductor 3.23 (current release, 2026) places the BSgenome framework among the cornerstone packages of the entire ecosystem. But BSgenome differs from every other Bioconductor cornerstone in one decisive way: it is **per-organism**, not universal. This shapes the entire argument.

By direct reverse-dependency count (`Depends`+`Imports`), BSgenome ranks **6th of all software packages** in Bioconductor 3.23:

| Rank | Package | Reverse deps | Type of dependency |
|---|---|---|---|
| 1 | S4Vectors | 1,018 | universal — one install serves every use case |
| 2 | IRanges | 725 | universal |
| 3 | SummarizedExperiment | 720 | universal |
| 4 | GenomicRanges | 604 | universal |
| 5 | Biostrings | 481 | universal |
| **6** | **BSgenome** | **350** | **per-organism — split into 121 software packages and 229 species-specific data packages** |
| 7 | GenomeInfoDb | 189 | universal |
| 8 | rtracklayer | 183 | universal |
| 9 | VariantAnnotation | 77 | universal |

**The decomposition of BSgenome's 350 reverse dependencies is the central observation of this paper.** Universal cornerstones like GenomicRanges or Biostrings have one install path: `BiocManager::install("GenomicRanges")` succeeds once and serves every genome, every assembly, every downstream analysis for the lifetime of the R installation. BSgenome does not work that way. To analyze human ChIP-seq data, a user installs `BSgenome.Hsapiens.UCSC.hg38`; to analyze the same workflow in mouse, the user must also install `BSgenome.Mmusculus.UCSC.mm10`; to analyze it in an organism not in the 33 pre-packaged species, **the user cannot proceed at all** until a corresponding BSgenome data package is built.

The 350 reverse-dependency total therefore decomposes into two structurally different layers:

- **121 software packages** that consume "some BSgenome" — the universal-style dependents. These are the working bioinformatics tools (full census below).
- **229 BSgenome.\* species-specific data packages** — the per-organism leaves of the dependency tree. Each one represents a single species × assembly combination that has been packaged by hand and hosted on Bioconductor.

The 121 software dependents span eight domains of working bioinformatics, confirmed against `bioconductor.org/packages/release/bioc/html/BSgenome.html`:

- ChIP-seq / peak analysis: ChIPanalyser, GreyListChIP, chromVAR, monaLisa, motifmatchr
- ATAC-seq: ATACseqQC, esATAC, SCOPE
- Bisulfite / methylation: bsseq, MEDIPS, methrix, MethylSeekR, REMP, methodical, qsea
- Variant calling / annotation: VariantAnnotation, VariantFiltering, VariantTools, gmapR
- CRISPR design: CRISPRseek, crisprDesign, crisprBowtie, crisprBwa, GUIDEseq
- Mutational signatures: MutationalPatterns, SigsPack, signeR, musicatk
- Visualization: Gviz, ggbio, GenVisR
- TSS / CAGE profiling: CAGEr, ORFik, cleanUpdTSeq

Real-world usage signal — Bioconductor 2024 download statistics (most recent complete year), from `bioconductor.org/packages/stats/`. Both distinct-IP and total-download metrics reported because they capture different signals (distinct IPs ≈ unique installers; total downloads ≈ CI runs, container builds, re-installs):

| Package | 2024 distinct IPs | 2024 total downloads |
|---|---|---|
| BSgenome (framework) | **149,515** | **404,453** |
| BSgenome.Hsapiens.UCSC.hg38 | 34,071 | 103,147 |
| BSgenome.Hsapiens.UCSC.hg19 | 25,436 | 61,853 |
| BSgenome.Mmusculus.UCSC.mm10 | 10,842 | 25,765 |
| GenomicRanges (universal-anchor) | 371,542 | 1,231,645 |
| Biostrings (universal-anchor) | 400,962 | 1,268,634 |

The BSgenome framework reaches ~40% of the distinct-IP count of GenomicRanges and ~33% of total downloads — solidly in the everyday-use tier, not the niche-utility tier. The hg38 + hg19 + mm10 model-organism data packages alone account for ~70,000 distinct IPs and ~190,000 downloads annually.

**1d. Same-track benchmark: BSgenome among Bioconductor's per-organism data-package families** (~120 w)

The right peer comparison for BSgenome is not universal-infrastructure cornerstones (GenomicRanges, Biostrings) but **other per-organism Bioconductor data-package families**. By package count in release 3.23 (parsed from the annotation `VIEWS` index):

| Family | Packages | Content |
|---|---|---|
| **BSgenome.\*** | **113** | Full genome sequences (2bit) |
| TxDb.\* | 48 | UCSC-style transcript annotations |
| org.\*.eg.db | 21 | Organism-level gene annotation databases |
| MafDb.\* | 14 | Minor allele frequency annotations |
| EnsDb.\* | 7 | Ensembl-derived transcript annotations |
| SNPlocs.\* | 6 | SNP location databases |

**BSgenome.\* is the largest per-organism data-package family in all of Bioconductor.** Per-package 2024 downloads place BSgenome.Hsapiens.UCSC.hg38 (34,071 distinct IPs / 103,147 total downloads) in the same tier as TxDb.Hsapiens.UCSC.hg19.knownGene (41,830 / 99,274) — second only to the universally-required `org.Hs.eg.db` (165,277 / 462,805) among per-organism data packages. The 113 BSgenome.\* packages are not a small or experimental corner of the ecosystem; they are the most-built per-organism data family Bioconductor offers, used at scale.

**Closing claim of §1**: BSgenome's per-organism cost model is the structural reason an accessibility gap exists at all. For every other Bioconductor cornerstone, "the package exists" is a one-time global event. For BSgenome, "the package exists" must be re-established for every species × assembly a researcher wants to study. The 121 software-package dependents are unlocked for a given organism only when a corresponding `BSgenome.<species>.<provider>.<assembly>` data package exists. This is the gate that §2 quantifies. (Every other per-organism family — TxDb, EnsDb, org.\*, SNPlocs, MafDb — suffers the same gate, at smaller scale. Discussion §D3 returns to this transferability briefly without claiming it as the paper's contribution.)

---

**2. The accessibility gap (300 w)**
- 113 pre-built packages on Bioconductor; 33 species covered.
- NCBI Datasets currently lists ~837 eukaryotic reference genomes; Ensembl release indexes 2,716 species across vertebrates/fungi/plants/protists.
- The gap is roughly 30× — almost any non-model organism a wet-lab researcher would pick today is not packaged.
- (TSSr user feedback paragraph cut per 2026-05-14 advisor discussion; the 196→121-software + 8-domain census above carries the motivation without anecdotal evidence.)

**3. Why the gap persists — the construction barrier (250 w)**
- Walk through the manual BSgenomeForge workflow: download FASTA, normalize headers, detect/declare circular sequences, write seed DCF file, convert to 2bit, build with R CMD, check, distribute.
- Each step has a footgun: header conventions differ across NCBI vs Ensembl; mitochondrial/plastid contigs need circular flags; seed-file fields are positional and undocumented; R CMD build has 8 GB tar limits on large genomes.
- Result: even motivated researchers abandon the workflow.

**4. autoBSgenome (100 w)**
- One-sentence problem statement: an accession should be enough.
- Two-sentence solution: web service + pre-built repository.
- Closes with the mission line: "no BSgenome should be hard to build."

---

## Methods (~900 words)

**M1. End-to-end pipeline (350 w)**
- Accession → metadata retrieval (NCBI Datasets API / Ensembl REST) → FASTA download → header normalization → circular-sequence detection → 2bit conversion → seed file synthesis → R CMD build → tarball delivery.
- Build jobs run with `timeout-minutes: 60` (well below the GitHub Actions hosted-runner 6 h ceiling); even the largest successful build to date used 35 min.
- Three format/runtime limits encountered during large-genome scale-up and the workarounds applied (compact table, not bullet prose):

  | Limit | Threshold | Workaround |
  |---|---|---|
  | GitHub Release single asset | 1.9 GiB | Route tarballs above threshold to Zenodo (50 GB / record) |
  | UCSC 2bit default index | 4 GB output | `faToTwoBit -long` for input FASTA > 12 GB |
  | R internal `utils::tar()` | 8 GB tarball | `R_BUILD_TAR=tar` (external GNU tar, POSIX pax) |

- Idempotent re-builds keyed on assembly accession + autoBSgenome version.

**M2. Circular-sequence detection (150 w)**
- Heuristic: organelle keyword match + length sanity check + explicit assembly-report flags.
- Why this matters: BSgenome's `circ_seqs` slot affects downstream coordinate logic.

**M3. Batch pre-build pipeline (250 w)**
- Cron-driven dispatcher walks NCBI/Ensembl assembly inventories.
- Per-genome build jobs with retry + circuit-breaker.
- Output: tarballs in a CRAN-like repository with browsable taxonomy tree.
- Implementation note (one paragraph, not a section): the service runs on Cloudflare Pages/Workers for frontend/API and GitHub Actions/Releases for compute and artifact distribution. **No marketing of free tier, zero cost, or sustainability claims.** Just stated as implementation.

**M4. Reproducibility (150 w)**
- All workflow files, scripts, Dockerfile, and seed-file templates in the public repo.
- Each pre-built package's release page links back to the exact workflow commit and inputs.

---

## Results (~1,200 words)

**R1. Single-accession build benchmark (400 w)**
- 33-genome benchmark across fungi/plants/vertebrates.
- Median 44 s for <100 MB, 2–5 min for vertebrate-scale, up to ~50 min for the largest tested (lungfish, 34.56 GB).
- Table + scatter plot of build time vs genome size.

**R2. Pre-built BSgenome repository — coverage (500 w)**
- 3,553 packages across 6 taxonomic divisions.
- Coverage figure: stacked bar / sunburst by NCBI taxonomy.
- Compare against the 113 Bioconductor-hosted packages: 30× expansion.
- Browse interface: taxonomy tree, accession search, source link (NCBI/Ensembl), FASTA ID preview.

**R3. Robustness in batch operation (250 w)**
- Out of N attempted builds, M succeeded on first try; failures concentrated in (a) Ensembl filename irregularities (handled by resolver fallback), (b) genomes whose assembly characteristics exceed free-tier runner capacity (see R4).
- Document the failure rate honestly. This is "the tool works at scale."

**R4. The contiguity ceiling — assembly fragmentation, not genome size, sets the practical build limit (350 w) — NEW SECTION**

- The intuitive expectation is that BSgenome construction scales with raw base count. Empirically, the binding constraint on free-tier GitHub Actions runners (16 GB RAM, ~88 GB usable disk) is per-sequence overhead in R during `forgeBSgenomeDataPkg` and `R CMD build`, not nucleotide volume.
- Same-infrastructure, same-step comparison across four large-genome stress tests:

  | Organism | Assembly | Raw size | Sequence records | Outcome | Wall-clock | Forge peak RSS |
  |---|---|---|---|---|---|---|
  | *Triticum aestivum* | IWGSC RefSeq v2.1 | 14.57 GB | ~21 scaffolds | ✅ | 12:05 | — |
  | *Pinus taeda* | Ptaeda2.0 | 22.10 GB | several thousand scaffolds | ✅ | 34:18 | — |
  | *Ambystoma mexicanum* | AmbMex60DD | 28.21 GB | **27,157 contigs** | ❌ OOM at R forge | — | exceeded 16 GB |
  | *Neoceratodus forsteri* | neoFor_v3.1 | **34.56 GB** | **46 chromosome-level seqs** | ✅ | 35:20 | **708 MB** |

- **Decisive contrast:** lungfish is 23% *larger* in base count than axolotl, yet uses ≳20× *less* peak R memory during forge, because its sequence count is 591× lower. This isolates assembly contiguity as the binding axis.
- Mechanistic interpretation: `forgeBSgenomeDataPkg` allocates per-record R objects; total in-memory footprint scales with sequence count × per-record overhead, not with cumulative sequence length. The same axis compounds at the 2bit storage layer — chromosome-level assemblies carry fewer block-index entries for `N` runs, approaching the theoretical 2-bit-per-base floor on disk.
- **Implication for the tool's audience:** chromosome-level reference assemblies — exactly the targets for which BSgenome packages are most useful in downstream analysis — build reliably on free-tier infrastructure well beyond previously conservative estimates. Highly fragmented draft assemblies (≳30,000 contigs) hit the ceiling earlier, regardless of base count.
- Practical guidance for users with fragmented drafts: optional `min_contig_length` filter at submission time (planned feature) recovers buildability by dropping short unplaced scaffolds.

(Section is independently citable as an empirical finding about Bioconductor's BSgenomeForge scaling behavior, even if a reader ignores the rest of the paper.)

---

## Discussion (~600 words)

**D1. Implications for non-model organism analysis (250 w)**
- BSgenome-dependent workflows are now available for the full breadth of sequenced eukaryotes.
- Concrete examples of analyses that become possible (one per major domain).

**D2. Limitations (250 w)**
- On GitHub Actions hosted runners (16 GB RAM, ~88 GB usable disk), chromosome-level assemblies have been successfully built up to 34.56 GB (Australian lungfish, 46 sequences). Two regimes currently fall outside this envelope:
  1. **Highly fragmented assemblies** (≳30,000 contigs) — R-side forge stage exceeds 16 GB RAM regardless of total base count (see R4). Mitigations: optional contig-length filter at submission, or self-hosted runner with more memory.
  2. **Very large genomes** (raw size ≳150 GB, e.g. *Paris japonica*, some *Fritillaria* spp.) — exceed runner disk envelope and Zenodo per-record 50 GB cap. Requires self-hosted runner and chunked artifact distribution; planned in `docs/SELF-HOSTED-RUNNER-PLAN.md`.
- User-provided FASTA not yet supported; only public-accession inputs through NCBI Datasets and Ensembl REST.
- A small set of Ensembl assemblies use non-standard filename patterns and require manual resolver entries; coverage of these is ongoing.
- Masked BSgenome variants are intentionally not provided, consistent with Bioconductor's `BSgenome` + `MaskerSet` overlay model.
- 34.56 GB is the **current** empirical ceiling, not a theoretical one. The architecture admits further upward stress testing on additional chromosome-level large-genome targets (e.g. African lungfish ~40 GB, conifer references in the 20–31 GB range).

**D3. Outlook (200 w)**
- Community contribution pipeline.
- R-universe integration.
- Possible extension to BSgenome variants (alternate haplotypes, T2T assemblies as they appear).
- **Transferability hint (one paragraph, ~80 w):** the accession-driven build pattern demonstrated here for BSgenome.\* extends naturally to Bioconductor's other per-organism data-package families — TxDb.\* (48 species), EnsDb.\* (7), org.\*.eg.db (21), SNPlocs.\* (6), MafDb.\* (14). Each suffers the same per-organism cost gate identified in §1, at smaller scale. This is noted as a downstream opportunity, not as a claim of the present work — autoBSgenome's contribution is concrete: closing the gap for the largest of these families.

---

## Figures and tables

**F1. autoBSgenome workflow** — accession-in → tarball-out, one panel per pipeline stage.
**F2. The accessibility gap** — 113 Bioconductor packages vs autoBSgenome coverage, by taxonomic division.
**F3. Build-time benchmark** — scatter, time vs genome size, with size-class medians.
**F4. The contiguity ceiling** — bar / scatter comparing the four large-genome stress tests (R4); contig-count axis vs forge-stage success / peak RSS. Visually disambiguates "raw size" from "sequence count" as the true scaling axis.
**F5. Repository browse interface** — screenshot of taxonomy tree + per-package landing page.
**T1. 196 Bioconductor packages depending on BSgenome** (kept from v2).
**T2. 33-genome benchmark** (kept from v2).
**T3. Per-division coverage** (NCBI vs Ensembl, packaged vs not).

---

## What's explicitly OUT of this draft

These were live in v3 Plan C and are now off the table for the paper itself. They may still live in repo documentation.

- "Tool longevity crisis" / Wren-citation opener.
- Counterfactual AWS/VPS cost analysis ($0 vs $50–500/mo).
- Failure-mode → migration-path matrix.
- Transferability section ("this architecture applies to other services").
- "Sustainable" as the missing letter in FAIR.
- Any claim or implication that the paper is about *how to build long-lived bioinformatics services*. It is about how to build BSgenome packages.

---

## Pre-submission checklist

- [ ] Confirm advisor signoff on this v4 outline (in addition to today's verbal discussion).
- [ ] Verify the 196-package Bioconductor dependency census is current.
- [ ] Finalize 3,553 coverage number once the batch is fully complete.
- [ ] Update F1 workflow figure to match current pipeline (post external-tar fix, post Ensembl resolver coverage).
- [ ] F2 coverage figure with both NCBI and Ensembl divisions.
- [ ] Slogan "no BSgenome is hard to build" placed as the closing line of the Introduction (decided 2026-05-14, not in abstract).
- [ ] Post to bioRxiv.
- [ ] NARGAB submission with fee-waiver request if needed.
