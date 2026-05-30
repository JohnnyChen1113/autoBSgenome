# Package provenance inventory

Snapshot date: 2026-05-30
Source inspected: `https://johnnychen1113.github.io/autoBSgenome/packages.json`

## Counts

| Metric | Count |
|---|---:|
| Total indexed packages | 2,911 |
| Package tarball URL present | 2,911 |
| GitHub-hosted tarballs | 2,881 |
| Zenodo-hosted tarballs | 30 |
| `provider="NCBI"` | 838 |
| `provider="Ensembl"` | 2,073 |
| Provider in package name matches `provider` field | 2,911 |
| Accession present in index | 2,889 |
| Accession missing in index | 22 |
| `seq_ids` present in index | 2,897 |
| `seq_ids` missing in index | 14 |

## Source clarity levels

### Provider-level source

All 2,911 packages have a clear provider-level source:

| Provider source | Count |
|---|---:|
| NCBI | 838 |
| Ensembl / EnsemblGenomes | 2,073 |

This answers the high-level question "was this build an NCBI build or an
Ensembl build?" The package name and `provider` field agree for every
indexed package.

### Current-index source URL

The current `packages.json` should not be treated as an authoritative
source URL record.

| Current `source_url` status | Count |
|---|---:|
| Correct NCBI source URL with accession | 824 |
| Ensembl package with NCBI URL artifact | 2,065 |
| Ensembl package with empty `source_url` | 8 |
| NCBI package with missing/broken source metadata | 14 |

So only 824 of 2,911 packages have a provider-correct `source_url` in the
current index. The remaining 2,087 need recovery or correction.

### Exact build/download provenance

No historical package currently has complete event-level provenance in
the index. The missing pieces are:

- exact FASTA URL used by the build
- exact workflow run id
- commit SHA of the build workflow
- download timestamp
- source FASTA checksum
- tarball checksum
- `data_source`, `species_url`, and `ensembl_group`

This means we can classify provider-level source for all packages, but
we cannot prove the exact historical download event from `packages.json`
alone.

## Recovery notes

- NCBI packages with a valid accession can be treated as NCBI Datasets
  builds.
- Ensembl packages should keep `provider="Ensembl"`. Their NCBI
  `source_url` values are an index-writer artifact, not evidence of NCBI
  FASTA bytes.
- Package tarballs preserve stronger metadata than the current index. For
  example, `BSgenome.Scerevisiae.Ensembl.ScYJM1355v1` has the correct
  Ensembl `source_url` inside its `DESCRIPTION`, even though the live
  index points to NCBI.
- At least one empty-index package,
  `BSgenome.Csavignyi.Ensembl.CSAV20`, also has a recoverable Ensembl
  `source_url` inside `DESCRIPTION`.
- The 14 NCBI packages missing accession/seq metadata are legacy
  anomalies. Their provider-level source is NCBI, but their exact
  accession/download record needs recovery from package `DESCRIPTION`
  and/or NCBI Assembly lookup.

## Practical interpretation

If "source" means provider/database, all 2,911 packages are classifiable.

If "source" means a correct `source_url` in the current index, only 824
are clean today.

If "source" means exact historical download event, the historical record
is incomplete for all packages and needs reconstruction.

## DESCRIPTION recovery dry run

Dry run date: 2026-05-30

Method: read each package tarball's `DESCRIPTION` from GitHub/Zenodo,
parse `provider` and `source_url`, and compare them with the current
index. This was a read-only scan; no metadata was changed.

### Repair-action categories

| Category | Count | Meaning |
|---|---:|---|
| Already valid in current index | 824 | Current `source_url` is already provider-correct. |
| Recover from `DESCRIPTION` | 2,063 | Current index is wrong/empty, but package `DESCRIPTION` has a provider-correct `source_url`. |
| `DESCRIPTION` empty/broken | 1 | Tarball was readable, but `source_url` is empty or unusable. |
| Provider/URL conflict | 0 | No readable package contradicted its indexed provider. |
| Tarball read failed after targeted retry | 23 | All are large Ensembl tarballs; these likely need near-full tarball reads because `DESCRIPTION` is after the `.2bit` payload. |

### Raw DESCRIPTION content categories

| DESCRIPTION result | Count |
|---|---:|
| Correct NCBI URL in `DESCRIPTION` | 830 |
| Correct Ensembl URL in `DESCRIPTION` | 2,050 |
| Empty/broken `source_url` in `DESCRIPTION` | 1 |
| DESCRIPTION read failed | 30 |

The targeted retry recovered 105 of the 128 repair-blocking failures:
51 with an 8 MB range retry, then 54 more with a 64 MB range retry.

The difference between "tarball read failed" (23) and "DESCRIPTION read
failed" (30) is that 7 failed reads are NCBI packages whose current
index URL is already valid, so they do not block the source-url repair.

The remaining 23 repair-blocking tarballs have GitHub asset sizes totaling
about 5.50 GiB; the largest single tarball is about 1.14 GB. A spot check
confirmed the package structure can place `DESCRIPTION` after
`inst/extdata/single_sequences.2bit`, so these failures are consistent
with insufficient range length rather than provider/source conflicts.

## Applied repair

Applied to `gh-pages/packages.json` on 2026-05-30 in commit `eb96a7f`
(`Fix package source URLs from DESCRIPTION metadata`).

The applied repair changed only `source_url` fields:

| Provider | Changed `source_url` count |
|---|---:|
| Ensembl | 2,050 |
| NCBI | 13 |
| Total | 2,063 |

Post-apply validation compared the pre/post `flat` package records and
found 2,063 `source_url` changes and 0 changes to any other package field.
