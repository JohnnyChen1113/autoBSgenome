# Build-mode selection — planning doc

**Status:** design draft, not yet implemented
**Motivation:** highly fragmented assemblies (≳30,000 sequence records) exceed
the R-side forge memory envelope on free-tier GitHub Actions runners (see
`LARGE-GENOME-BENCHMARKS.md` for the contiguity-ceiling evidence). A full-FASTA
build is not always feasible or appropriate. Users should be able to choose
how the input FASTA is reduced before BSgenome construction.

## Proposed modes

| Mode | Identifier | Behavior |
|---|---|---|
| Full | `full` | Default. Build from the published FASTA as-is. No filtering. |
| Chromosomes only | `chromosomes` | Keep only records flagged as chromosomes (by assembly report or header pattern). Drop unplaced/unlocalized scaffolds. |
| Top-N by length | `top_n` | Keep the N longest sequence records, regardless of placement status. User supplies N. |
| Length threshold | `min_length` | Keep records whose length ≥ threshold in bp. User supplies threshold. |
| Cumulative-length percentile | `coverage_pct` | Sort records by length descending; keep enough to cover X% of total assembly length. User supplies X (e.g. 99%). |

The five modes together cover the common user mental models:
- "Just give me the reference karyotype" → `chromosomes`
- "I know my analysis needs the top 20 scaffolds" → `top_n`
- "Drop anything below 10 kb" → `min_length`
- "I want 99% of the genome but none of the long tail" → `coverage_pct`
- "Don't touch anything" → `full`

## Open design questions

1. **Package naming. [DECIDED 2026-05-14]** Filter is encoded inside the
   **4th name segment** via camelCase concatenation, NOT as a separate 5th
   segment. The 4-segment shape `BSgenome.<species>.<source>.<assembly>`
   remains invariant; the assembly segment grows.

   Examples for *Triticum dicoccoides* WEW_v2.1 under each mode:

   | Mode | Package name |
   |---|---|
   | `full` (default) | `BSgenome.Tdicoccoides.NCBI.WEWv21` |
   | `chromosomes` | `BSgenome.Tdicoccoides.NCBI.WEWv21Chr` |
   | `top_n` (N=200) | `BSgenome.Tdicoccoides.NCBI.WEWv21Top200` |
   | `min_length` (10 kb) | `BSgenome.Tdicoccoides.NCBI.WEWv21Min10kb` |
   | `coverage_pct` (99%) | `BSgenome.Tdicoccoides.NCBI.WEWv21Cov99` |

   Suffix tokens are short, lower-case-first camelCase fragments appended
   directly to the assembly token (no separator). `full` has no suffix.

   Rationale: keeps the canonical 4-segment Bioconductor naming convention.
   Namespace expansion is acceptable — Bioconductor's official BSgenome
   namespace already carries multiple variants of the same assembly
   (`BSgenome.Hsapiens.UCSC.hg38`, `.hg38.masked`, etc.), so the precedent
   is established.

2. **What carries the filter through the pipeline?**
   - Web UI / API request body: `build_mode` + `build_mode_param`.
   - Worker dispatch payload: same two fields.
   - GitHub Actions workflow inputs: same two fields.
   - Build script: applies filter as a Python preprocessing step after FASTA
     download, before `faToTwoBit`.
   - Seed file: records `BSgenomeObjname` + filter metadata as comments.
   - Package `DESCRIPTION`: records filter mode + parameters in a custom
     `BuildMode:` field.

3. **Chromosome detection logic.** Two valid heuristics:
   - NCBI assembly report `Sequence-Role: assembled-molecule` lines.
   - Header pattern match: chromosomes typically have header containing
     `chromosome <N|X|Y|MT>`.

   Prefer the assembly-report path when available; fall back to header
   pattern. Both should be unit-tested against a small bank of edge-case
   genomes (mitochondria, plastids, alt haplotypes, sex chromosomes).

4. **Circular-sequence detection under filtering.** Today's logic flags
   organelle contigs (mt, chloroplast) as circular. If `chromosomes` mode
   drops organelles, the filter shouldn't break the circular detection
   step — needs explicit handling.

5. **Coverage-percent mode and the long tail.** `coverage_pct=99` on wild
   emmer wheat would still leave a non-trivial scaffold count (since the 14
   chromosomes are ~99% by length but the tail is 148k short scaffolds). We
   need to verify by simulation before promising this mode to users.

6. **Display in the web UI.** The mode selector needs:
   - A preview pane showing "after filtering: X chromosomes + Y scaffolds,
     covering Z% of total length, Σ bp" before the user submits.
   - This requires either a pre-flight API call that fetches the assembly
     report, or client-side computation if the report is small.

7. **Catalog/browse-page handling.** Filtered variants need to be browsable
   alongside full builds. Likely a small column or badge on each package's
   landing page: "Build mode: full" or "Build mode: chromosomes only (14
   sequences out of 148,296)".

## Implementation order (suggested)

1. Backend filter logic (Python, between FASTA download and 2bit) with
   unit tests for the five modes.
2. Workflow input plumbing (`build-bsgenome.yml` accepts `build_mode` +
   param).
3. Worker API accepts the two fields and forwards to dispatch.
4. Web UI mode selector + preview pane.
5. Package-name suffix scheme (after deciding option (a) vs (b)).
6. Catalog page badges.

Each layer is independently testable, so we can validate (1) against the
wild emmer wheat case before touching the UI.

## First validation target

**Wild emmer wheat (*Triticum dicoccoides*, GCF_002162155.2, WEW_v2.1)** —
10.68 GB total, 14 chromosomes, scaffold N50 = 747 Mb, but **148,296
scaffolds total**. A `chromosomes`-mode build should be trivially fast on
free-tier runners (14 records). A `coverage_pct=99` build is the more
interesting test: it isolates how much of the long tail survives at the
99th percentile.

## Related

- `LARGE-GENOME-BENCHMARKS.md` — empirical basis for needing this feature.
- `paper/draft-v4-outline.md` R4 "contiguity ceiling" — this feature is the
  user-facing mitigation cited at the end of that section.
- `docs/SELF-HOSTED-RUNNER-PLAN.md` — alternative path (more memory rather
  than less input) for the same problem.
