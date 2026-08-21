# Large-genome stress-test roster

The active roster is the 16-entry NCBI campaign defined in
[`large-genomes-2026.json`](../.github/benchmarks/large-genomes-2026.json).
This document describes why the set was selected; the manifest is authoritative
for accession, assembly name, release date, total length, scaffold count, N50,
version, and execution order.

## Design

The roster deliberately spans both total assembly length and contiguity:

- 9.35–19.77 Gbp includes highly contiguous assemblies and two assemblies with
  more than 11 million scaffolds.
- 22.10–28.21 Gbp includes 17-scaffold chromosome-scale input, intermediate
  assemblies, and assemblies with 1.76–4.25 million scaffolds.
- 34.56–48.15 Gbp extends beyond the previous largest successful observation,
  the 34.56-Gbp Australian lungfish assembly.

The campaign includes:

1. *Triticum timopheevii*
2. *Ambystoma mexicanum*
3. *Taxus chinensis*
4. *Picea abies*
5. *Larix sibirica*
6. *Triticum aestivum*
7. *Allium cepa*
8. *Pleurodeles waltl*
9. *Pinus taeda*
10. *Pinus tabuliformis*
11. *Sequoia sempervirens*
12. *Picea glauca*
13. *Pinus lambertiana*
14. *Neoceratodus forsteri*
15. *Protopterus annectens*
16. *Paris polyphylla* var. *yunnanensis*

The first run validates the metrics path. The second directly retests the
historical *A. mexicanum* failure. Remaining inputs then proceed in increasing
size order.

## Interpretation rules

- Run every listed accession once; do not silently substitute another assembly.
- Continue the campaign after individual failures.
- Do not label a failure OOM, disk exhaustion, timeout, or download failure
  without the recorded stage and direct error evidence.
- Treat NCBI scaffold count and actual downloaded FASTA record count as separate
  measurements.
- Do not infer a causal size or contiguity ceiling from one comparison.
- Report single-run elapsed times as observational values without variance or
  confidence intervals.

## Publication policy

Before each dispatch, compare the live package index using both provider and
accession. Exact existing NCBI packages are measured but not uploaded again.
Existing Ensembl packages do not conflict with new NCBI packages because their
provider-qualified package identifiers differ.
