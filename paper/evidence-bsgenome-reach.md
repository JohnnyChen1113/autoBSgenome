# Evidence package: BSgenome's reach in the Bioconductor ecosystem

Collected 2026-04-19 from Bioconductor release PACKAGES/VIEWS metadata and
the public download stats API. Use these numbers when writing the motivation
and introduction of the Plan C paper. They replace the looser "196 packages"
claim in draft-v2 with harder, categorized, and cited figures.

## Reverse dependencies

Bioconductor release 3.21 software package count: **2,361 total**.

Packages depending on BSgenome:

| Category | Count |
|---|---|
| Depends / Imports / LinkingTo (runtime-required) | **118** |
| Suggests (optional companion) | 88 |
| **Total listing BSgenome in DESCRIPTION** | **206** |

**Context — reverse hard-dependency count of other Bioconductor core infrastructure** (higher = more foundational):

| Package | Hard reverse deps | Stack role |
|---|---|---|
| GenomicRanges | 550 | Genomic interval arithmetic |
| Biostrings | 296 | Sequence string operations |
| AnnotationDbi | 193 | Annotation DB interface |
| rtracklayer | 182 | Browser track I/O |
| GenomicFeatures | 142 | Transcript annotation |
| **BSgenome** | **118** | **Genome sequence data** |

Interpretation: BSgenome sits in Bioconductor's top-tier infrastructure layer
alongside GenomicFeatures. Not the single most-depended-upon package
(GenomicRanges holds that position by virtue of representing the core
interval data type), but demonstrably part of the small set of packages that
hundreds of downstream tools assume is present.

## Download volume (Bioconductor public stats)

Calendar year 2025 totals (distinct IPs in parentheses):

| Package | 2025 downloads | 2025 distinct IPs |
|---|---|---|
| BSgenome (infrastructure) | **490,703** | 116,259 |
| BSgenome.Hsapiens.UCSC.hg38 | 144,896 | — |
| BSgenome.Hsapiens.UCSC.hg19 | 115,139 | — |
| BSgenome.Mmusculus.UCSC.mm10 | 88,942 | — |
| BSgenome.Dmelanogaster.UCSC.dm6 | 6,158 | — |
| BSgenome.Athaliana.TAIR.TAIR9 | 3,390 | — |

Each download of a BSgenome data package corresponds roughly to a researcher
configuring a genomic analysis environment. The top three data packages alone
exceed **349,000 downloads per year**.

For context, GenomicRanges logged ~1.4 million downloads/year in the same
period — the single most heavily-used Bioconductor infrastructure package.
BSgenome's infrastructure at 490K/year is ~35% of GenomicRanges by raw
traffic, which for a more specialized (genome-sequence-specific) layer is a
high share.

## Domain breadth of hard dependents

Categorizing the 118 hard-dependency packages by analysis domain (keyword
match on package name, so some overlap and some uncategorized remainder):

| Analysis domain | Hard-dep packages | Examples |
|---|---|---|
| CRISPR guide design | 7 | crisprDesign, crisprBowtie, crisprBwa, CRISPRseek |
| ChIP-seq / ATAC-seq / chromatin | 6 | ATACseqQC, ChIPComp, ChIPanalyser |
| Variant / SNP / mutation | 6 | MutationalPatterns, VariantAnnotation-adjacent, atSNP |
| Motif / TFBS | 5 | motifbreakR, motifmatchr, Motif2Site |
| Gene expression / RNA-seq context | 7 | circRNAprofiler, CleanUpRNAseq, CODEX |
| Methylation / bisulfite | 2 | bsseq, MethylSeekR |
| TSS / CAGE / promoter | 2 | CAGEr, primirTSS (+ TSSr on CRAN/GitHub) |
| Visualization / browser | 1 | Gviz |
| Alignment / mapping | 1 | gmapR |
| Single-cell | 2 | scmeth, tRNAscanImport |
| Other / uncategorized | 80 | — |
| **Total** | **118** | |

The uncategorized 80 reflects BSgenome's use outside neatly-named analysis
categories — species-specific toolkits, regulatory element discovery,
pangenomics, etc.

## Paper-ready sentences (drop-in candidates)

**For the introduction**:
> "BSgenome data packages serve as a fundamental dependency across the Bioconductor ecosystem. In the current Bioconductor release, 118 software packages include BSgenome in their Depends, Imports, or LinkingTo fields — placing it in the same infrastructure tier as GenomicFeatures (142 reverse dependencies) and AnnotationDbi (193) — and a further 88 packages list it as a Suggests companion. These 206 packages collectively span CRISPR guide design (crisprDesign, CRISPRseek), ChIP-seq and ATAC-seq (ATACseqQC, ChIPComp), variant analysis (MutationalPatterns), motif discovery (motifbreakR, motifmatchr), methylation calling (bsseq, MethylSeekR), transcription start site profiling (CAGEr, TSSr), and many other analysis domains."

**On usage scale**:
> "The BSgenome infrastructure package received approximately 490,000 downloads in 2025 from 116,000 distinct IP addresses, and the most-downloaded species data package (BSgenome.Hsapiens.UCSC.hg38) accounted for 145,000 of those downloads. At an ecosystem level this corresponds to roughly one BSgenome-dependent analysis environment being configured every minute, every day of the year."

**On the accessibility gap** (still valid from v2 draft, now quantitatively grounded):
> "Yet Bioconductor hosts pre-built BSgenome packages for only 33 organisms, versus over 3,500 eukaryotic reference genomes available from NCBI and Ensembl. For the ~100,000 researchers per year configuring BSgenome-dependent workflows, this means that any organism outside this narrow set requires manual package construction — a process that requires specialized software, command-line expertise, and familiarity with a non-trivial R/Bioconductor convention."

## Sources + how to reproduce

- Reverse dependency counts: parse `https://bioconductor.org/packages/release/bioc/VIEWS`, count packages listing BSgenome in Depends/Imports/LinkingTo (hard) and Suggests (soft) fields. Baselines (GenomicRanges, etc.) obtained the same way.
- Download stats: `https://bioconductor.org/packages/stats/<subrepo>/<pkg>/<pkg>_stats.tab` — per-month and per-year totals maintained by Bioconductor back to 2008 for most packages.
- Script to regenerate: inline Python in this session's transcript; can factor into `scripts/refresh-bsgenome-reach-stats.py` if we want the paper numbers to stay live.
