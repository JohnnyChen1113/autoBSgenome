# Large-genome stress-test roster

The active roster is the 20-entry NCBI campaign defined in
[`large-genomes-2026.json`](../.github/benchmarks/large-genomes-2026.json).
This document describes why the set was selected; the manifest is authoritative
for accession, assembly name, release date, total length, scaffold count, N50,
version, and execution order.

## Design

The roster deliberately spans both total assembly length and contiguity:

- every assembly is larger than 20 Gbp;
- the 21.93–29.02 Gbp range spans 17 to 9.39 million scaffolds;
- the 34.56–48.15 Gbp range includes both highly contiguous and million-record
  inputs; and
- the 87.22- and 94.26-Gbp assemblies test the largest current public NCBI
  references available for this campaign.

The campaign includes:

1. *Pleurodeles waltl*
2. *Pinus taeda*
3. *Pinus radiata*
4. *Calotriton arnoldi*
5. *Lissotriton helveticus*
6. *Lissotriton vulgaris*
7. *Pinus tabuliformis*
8. *Picea engelmannii*
9. *Sequoia sempervirens*
10. *Picea glauca*
11. *Pinus lambertiana*
12. *Pinus albicaulis*
13. *Ambystoma mexicanum*
14. *Ambystoma opacum*
15. *Neoceratodus forsteri*
16. *Euphausia superba*
17. *Protopterus annectens*
18. *Paris polyphylla* var. *yunnanensis*
19. *Lepidosiren paradoxa*
20. *Viscum album*

The first three entries form the initial workflow-validation batch. The
orchestrator is dispatched with `through_order: 3`, so orders 4–20 are skipped
without being removed from the manifest. The historical *A. mexicanum* failure
remains in the full campaign at order 13.

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
The manifest additionally pins `publication_policy: never` for *Pinus taeda*
`GCA_000404065.3` and *Neoceratodus forsteri* `GCA_016271365.2`, so those two
reruns cannot publish even if the live index is incomplete. Existing Ensembl
packages do not conflict with new NCBI packages because their
provider-qualified package identifiers differ.
