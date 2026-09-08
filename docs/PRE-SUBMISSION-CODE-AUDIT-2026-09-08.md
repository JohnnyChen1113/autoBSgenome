# Pre-submission code audit

Date: 2026-09-08. Status: code merged and deployed; hosted build, installation,
and sequence verification passed. This review preserves the existing CLI/documentation work
and adds no browser extension, account requirement,
WebMCP integration, or new end-user setup step.

## Assessment

The project has a workable separation between the Web UI, API Worker, build
workflow, and sequence-processing helpers. Its main weaknesses were boundary
validation, duplicated single/batch metadata handling, and tests that checked
source text without exercising the resulting build or browser behavior.
Before submission, fixing these demonstrated failures is more appropriate
than restructuring the application.

## Confirmed findings and fixes

| Priority | Reproduced problem | Correction |
| --- | --- | --- |
| High | Public metadata became executable shell text; generated R and Rd templates also accepted executable expressions. | Environment bindings, atomic input validation, Python seed writing, and literal R/Rd template rendering before package build. Harmless execution-marker regressions cover all three contexts. |
| High | Ensembl candidate/fallback searches could return a different assembly; strain slugs were truncated and Plants/Fungi source information could be lost. | Verify the requested assembly in each FASTA filename, handle authoritative patch-name aliases, preserve complete slugs and divisions through single and batch dispatch, and keep CLI source identity separate from editable labels. |
| High | An existing release could be reused despite different archive bytes, attaching new provenance to an old artifact. | Require exact filename, byte size, and SHA-256; preserve the release and stop index publication on mismatch. |
| Medium | Upload size limits depended on client declarations and multipart completion did not verify actual bytes. | Bind size into new signed URLs, validate part order/count/length, reject invalid completed objects, and recheck stored size before dispatch. Earlier signed URLs remain supported. |
| Medium | Cancelled, timed-out, failed, and expired builds could poll indefinitely; a release without a usable tarball could look successful. | Interpret terminal workflow state even without a failure release, report expiry, and require a published nonempty BSgenome tarball for success. |
| Medium | Failed batch jobs prevented results access; metadata shard effects cancelled their own successful requests. | Count failed jobs as finished, preserve server error details, clean up polling, and let metadata requests complete across state/filter changes. |
| Medium | The CLI used a now-defunct BSgenome forge entry; user R startup profiles changed output directories; macOS tar attributes broke R unpacking. Corrupt gzip input could leave an incomplete FASTA. | Call BSgenomeForge explicitly, isolate R startup profiles, exclude macOS archive metadata, clean partial decompression outputs, retain existing FASTA files, and offer the local fallback. |
| Medium | Submitted descriptions were discarded; release-date formatting could shift calendar month; cleanup errors were swallowed. | Preserve submitted metadata through seed/package generation, use upstream calendar dates, and make release cleanup select its repository explicitly and surface failures. |

Principal code locations: `autoBSgenome.py`, `scripts/build_input.py`,
`scripts/resolve_ensembl_fasta.py`, `scripts/verify_release_asset.py`,
`.github/workflows/build-bsgenome.yml`, `.github/workflows/cleanup-releases.yml`,
`worker/src/index.ts`, and the Web build/catalog features.

## Verification

The automated suites passed 156 tests in total. The Python run included the
native R/Rd execution and metadata-preservation regression, with BSgenomeForge
available through an isolated temporary R library.

| Check | Result |
| --- | --- |
| Python tests | 121 passed (`python3 -m unittest discover -s tests -q`) |
| Worker tests | 21 passed |
| Web tests | 14 passed |
| Web TypeScript, ESLint, Cloudflare production build | Passed; existing nonfatal Nitro/configuration warnings remain |
| Browser single/batch workflows | Passed with all external requests intercepted; no real dispatch |
| Browser metadata-shard race | Reproduced before fix; common-name and taxonomy metadata render after fix, including filter changes during loading |
| Local workerd and emulated R2 | Real HTTP multipart upload, completion and download passed with byte equality |
| Workflow YAML and shell syntax | Both changed workflows parse; all 20 build-workflow shell steps pass `bash -n` |

The complete native build/install/sequence comparison passed on macOS with
R 4.6.0, BSgenome 1.80.0, BSgenomeForge 1.12.0, and UCSC `faToTwoBit`.
`build_package()` built the repository fixture
`test_data/GCF_016861625.1_AkawachiiIFO4308_assembly01_genomic.fna`, and
`R CMD INSTALL` installed the resulting archive into a temporary library.
`Biostrings::readDNAStringSet()` and `getSeq()` confirmed identical sequence
names, lengths, and every base across all 9 sequences (37,287,723 bases).
After the final macOS tar correction, all 27 CLI tests were also rerun and
passed. `git diff --check` passed.

The pinned builder uses R 4.4.0, Bioconductor 3.20, and BSgenomeForge 1.6.0.
Both native R metadata/security regressions also passed inside that Linux
build stack in [run 34227950501](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/34227950501).
The builder workflow now runs these regressions when the helper, tests, or
relevant workflows change.

Browser checks included desktop (1365 x 1000) and mobile (390 x 844)
screenshots. Temporary Playwright/R/UCSC tooling was installed outside the
repository, without changing project runtime dependencies or the user's R
library. Three older workflow tests now follow the actual environment/helper
flow. The sampler termination test waits for its first sample instead of
assuming Python installs signal handlers within 250 ms.

## Production rollout

The main audit was merged in [PR 22](https://github.com/JohnnyChen1113/autoBSgenome/pull/22)
at `34878bc4980f944ac50abcb238d6e3e395afe29e`. Frontend deployment
[34225850293](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/34225850293)
completed both production and fallback deployment steps, without skipping them.

| Component | Published version |
| --- | --- |
| `autobsgenome.org`, `www.autobsgenome.org` | Worker `2097f5e8-b473-43af-80ad-dd72fa15e68b` |
| `autobsgenome.bioinfoark.workers.dev` fallback | Worker `44995e6d-47b6-48f4-b369-f161a7c60405` |
| `api.autobsgenome.org` | Worker `1d7b4f3c-1d8f-43d4-b14c-7da55b0d30c8` |

The first hosted acceptance attempt exposed an additional input-handling bug:
BSgenomeForge rejected the literal `@PKGTITLE@` in the test description before
the safe renderer ran. This also reproduced locally, so it was a missing
full-flow test rather than a Linux-only bug. A protected forge seed and complete
metadata restoration fixed it in [PR 23](https://github.com/JohnnyChen1113/autoBSgenome/pull/23),
merged as `9b5c36d9845b952adc38308916bbccb054771b46`. The actual-forge regression
also covers unknown placeholder tokens and filesystem paths with repeated spaces.

All three repeated hosted builds completed successfully using that exact
commit and the workflow's pinned builder image. Their archives were downloaded
through the public package URLs and installed into an isolated temporary R
library on macOS. Sequence names, lengths, and every base matched the source
FASTA, covering 28 sequences and 49,444,866 bases. Each installed package also
preserved this description exactly: `Hosted acceptance: "quoted" metadata, @PKGTITLE@, 100% {literal braces}.`

| Source | Job | Successful workflow | Identical sequences | Identical bases |
| --- | --- | --- | ---: | ---: |
| NCBI `GCF_016861625.1` | `3e9d3b84` | [34228499074](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/34228499074) | 9 | 37,287,723 |
| Ensembl Fungi, *S. cerevisiae*, `R64-1-1` | `d0d92bed` | [34228506079](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/34228506079) | 17 | 12,157,105 |
| Uploaded synthetic FASTA | `e343f35c` | [34228511395](https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/34228511395) | 2 | 38 |

The downloaded archives had the byte sizes reported by the API. SHA-256 values
identify the installed artifacts after their temporary releases expire:

| Job | Archive bytes | SHA-256 |
| --- | ---: | --- |
| `3e9d3b84` | 9,752,890 | `454740e0e9c5c2b040f4c57339bdab86e86cb3364e8b685f4903bbb42addfe20` |
| `d0d92bed` | 2,966,414 | `4d670be491cb1315f76434d5ea18b00fd0dab2628ea6408dce2126efffa51866` |
| `e343f35c` | 1,890 | `4f754d35dd5e67222dab94c37c4524daae94c5d11bd506090c6f4a8669bbf7bc` |

Live browser checks confirmed HTTP 200 responses, interactive build controls,
and catalog access, with no uncaught JavaScript errors or mobile horizontal
overflow. Desktop and mobile screenshots were inspected. Acceptance outputs
use normal two-day temporary retention and do not enter the permanent index.

## Remaining limits

1. These checks cover small representative builds and do not replace the
   existing large-genome benchmarks or prove every upstream failure mode.
2. Ensembl filename checks reject a different named assembly, but cannot prove
   accession revisions when upstream reuses the same assembly filename.
3. Status reconstruction searches at most 300 recent runs. An old job with no
   remaining release and no discoverable run still cannot be classified
   reliably. Durable status storage remains a separate improvement.
4. Existing product limits remain: temporary packages above approximately
   1.9 GiB are not published, and no new authentication/challenge requirement
   has been added. This audit is not an exhaustive public-service abuse review.
