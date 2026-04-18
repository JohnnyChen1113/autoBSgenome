# Cancelled Builds Registry

Tracking runs of `build-bsgenome.yml` that were cancelled (not failed) — typically
from hitting the 30-minute `timeout-minutes` wall. Use this to calibrate size
thresholds and to decide what warrants workflow tuning vs. falling back to manual
handling on a bigger machine.

## Schema

Each entry captures:

- **Organism** — scientific name as it appears in the queue
- **Accession** — GenBank/RefSeq identifier
- **Assembly** — assembly name used in the package name
- **Genome size** — raw genome size in MB (from NCBI assembly report)
- **Data source** — NCBI or Ensembl
- **Estimated tarball size** — based on observed ratio (~18% of genome size for 2bit-format BSgenome packages; updated from successful builds of similar size)
- **Run URL** — GitHub Actions run for diagnostics
- **Cancelled at step** — which step hit the wall
- **Duration before cancel** — how long it ran (tells us whether it was close to finishing or fundamentally stuck)
- **Release state after cancel** — `draft` (incomplete upload), `published` (prior successful build's release still exists), or `none`
- **Analysis note** — our interpretation / follow-up

## Known successful size ceiling

| Organism | Genome | Tarball | Built status |
|---|---|---|---|
| **Hordeum vulgare cv. DuLiHuang** | **~5.3 GB** | **1.00 GB** | ✅ done (retested 2026-04-18 after fix, took 3 min 42 s total) |
| Triticum urartu (wild wheat) | 4.85 GB | ~900 MB (est) | ✅ done |
| Orycteropus afer (aardvark) | 4.44 GB | 893 MB | ✅ done |
| Chrysochloris asiatica (Cape golden mole) | 4.21 GB | 881 MB | ✅ done |
| Aegilops tauschii (goatgrass) | 4.12 GB | ~800 MB | ✅ done |
| Nicotiana tabacum (tobacco) | 4.00 GB | — | ✅ done |

**Empirical ceiling (as of 2026-04-18): the system has successfully produced packages for genomes up to ~5.3 GB.** Cancellations below that size are not size-limited — they are transient upload/network issues.

### Re-test results (post-fix)

Re-dispatched the Hordeum DuLiHuang cultivar that had cancelled on 2026-04-17 after applying the timeout-60 + skip-upload fixes. Run `24615911380`, step-level timing:

| Step | Duration |
|---|---|
| Download FASTA from Ensembl | 43 s |
| Convert FASTA to 2bit | 24 s |
| Generate seed file + R CMD build | 68 s |
| Create GitHub Release | 35 s |
| Publish to permanent repository | **25 s** (cancelled at 30 min on prior run) |
| **Total** | **3 min 42 s** |

The 25-second publish step confirms the previous cancellation was a transient runner-bandwidth fluke, not a structural limit. Current runner achieved ~40 MB/s upload for the 1 GB tarball.

## Cancelled runs

### 2026-04-17

#### Hordeum vulgare cv. DuLiHuangZDM01467BPG v2

- **Accession**: GCA_949783385.1 (as part of the Ensembl pan-barley dataset)
- **Assembly**: HvulgarecvDuLiHuangZDM01467BPGv2
- **Genome size**: ~4.8-5.3 GB (typical barley cultivar assembly; exact figure not populated in queue)
- **Data source**: Ensembl (EnsemblPlants)
- **Estimated tarball size**: ~900 MB - 1 GB
- **Run URL**: <https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24589866475>
- **Cancelled at step**: `Publish to permanent repository`
- **Duration before cancel**: 30 min 05 s (exactly at timeout)
- **Release state after cancel**: `draft: true` (interrupted upload, leftover draft release in repo)
- **Analysis note**: All upstream steps (FASTA download, 2bit, R CMD build, Release create) succeeded. Failure was in tarball upload to GitHub Releases. Similarly-sized wheat (4.85 GB) succeeded on a different run, so this is **not a size ceiling** — it is a per-run transient issue (runner bandwidth, API contention, or both). Leaves behind a draft release that will block re-runs unless cleaned up.

#### Arachis hypogaea cv. Tifrunner

- **Accession**: GCA_003086295.3
- **Assembly**: arahyTifrunnergnm2J5K5
- **Genome size**: 2557 MB (2.56 GB)
- **Data source**: Ensembl (EnsemblPlants)
- **Estimated tarball size**: ~500-600 MB
- **Run URL**: <https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/24568676013>
- **Cancelled at step**: `Publish to permanent repository`
- **Duration before cancel**: 30 min 06 s (exactly at timeout)
- **Release state after cancel**: `published` — an earlier successful run had already published `pkg-BSgenome.Ahypogaea.Ensembl.arahyTifrunnergnm2J5K5`. This cancelled run was a redundant re-dispatch caused by the queue's stale `building` status (fixed in commit `1d31b7d`).
- **Analysis note**: **This package actually exists** (earlier run published it). The cancelled run was a wasted re-build, not a real failure. Pre-2.6 GB should be comfortably within system capacity — system has demonstrably built 4.85 GB genomes.

## Interpretation

**Neither cancelled run represents a genuine size limit.** Both were transient failures during GitHub Release tarball upload. System capacity (proven empirically) is at least 4.85 GB genome → 900 MB tarball.

## Hypotheses for why uploads cancel

1. **GHA runner bandwidth variance** — free-tier runners have unpredictable upstream bandwidth; a 900 MB upload at 1 MB/s takes 15 min, but at 200 KB/s takes 75 min (> 30 min timeout).
2. **Concurrent API contention** — when 10-20 builds finish near-simultaneously and all try to upload to Releases, GitHub may throttle them.
3. **Redundant re-builds** (peanut case) — the queue-status bug caused duplicate dispatches for items already published; `gh release delete` then re-upload wastes the budget.

## Proposed fixes (in order of cost)

1. **Skip `gh release delete` when the existing release's tarball matches our current tarball size/hash** — avoids wasted re-uploads for items that already exist. (cheap)
2. **Raise `timeout-minutes` from 30 to 60** — absorbs transient upload slowness; no downside since GHA for public repos is free. (cheap)
3. **Clean up orphan draft releases on each run start** — prevents partial-upload artifacts from blocking retries. (cheap)
4. **For genomes > some threshold (TBD, but likely > 6 GB), skip the "Publish to permanent repository" step** — keep the Bioconductor tarball only as a GitHub Release artifact, not a CRAN-like entry. Users can still `install.packages()` via the direct Release URL. (moderate, requires API work)
5. **Split the upload across a separate workflow with a longer timeout** — moves the upload out of the 30-min build job. (expensive)

## Candidates for a "skip_oversized" threshold

We do not yet have evidence of a hard size ceiling. Current thinking:

- **< 3 GB**: should always work (peanut cancel was spurious)
- **3-5 GB**: works empirically (wheat, aardvark, mole, goatgrass, tobacco all done)
- **5-6 GB**: untested in autoBSgenome; some barley cultivars live here
- **> 6 GB**: wheat (~15 GB) falls here; likely genuinely beyond our upload envelope
- **> 10 GB**: known oversized, already tagged `skip_oversized` at queue-generation time (1 item currently)

After the proposed fixes land, re-run the two cancelled items and a couple of 5-6 GB candidates to pin down where the real wall is.

## Action items

- [ ] Apply proposed fixes #1–#3 (cheap) to `build-bsgenome.yml`
- [ ] Clean up the leftover draft release for the Hordeum cultivar
- [ ] Re-dispatch Hordeum vulgare DuLiHuang pan-barley cultivar after fixes
- [ ] Confirm peanut is a no-op (release already exists) — remove duplicate dispatch pressure by letting the queue sync catch up
- [ ] After fixes prove out on 5-6 GB genomes, decide empirical threshold for auto-skip
