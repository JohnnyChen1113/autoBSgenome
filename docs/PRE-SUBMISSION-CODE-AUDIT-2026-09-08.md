# Pre-submission code audit

Date: 2026-09-08. Initial audit status: local verification complete; deployment
and hosted acceptance are recorded separately when complete. This review preserves the existing
CLI/documentation work and adds no browser extension, account requirement,
WebMCP integration, or new end-user setup step.

## Assessment

The project has a workable separation between the Web UI, API Worker, build
workflow, and sequence-processing helpers. Its main weaknesses were boundary
validation, duplicated single/batch metadata handling, and tests that checked
source text without exercising the resulting build or browser behavior.
Before submission, fixing these demonstrated failures is more appropriate
than restructuring the application.

## Confirmed findings and fixes

| Priority | Reproduced problem | Local correction |
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

The automated suites passed 155 tests in total. The Python run included the
native R/Rd execution and metadata-preservation regression, with BSgenomeForge
available through an isolated temporary R library.

| Check | Result |
| --- | --- |
| Python tests | 120 passed (`python3 -m unittest discover -s tests -q`) |
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

The pinned builder uses R 4.4.0, Bioconductor 3.20, and BSgenomeForge 1.6.0;
its template placeholders were checked against that release's source.

Browser checks included desktop (1365 x 1000) and mobile (390 x 844)
screenshots. Temporary Playwright/R/UCSC tooling was installed outside the
repository, without changing project runtime dependencies or the user's R
library. Three older workflow tests now follow the actual environment/helper
flow. The sampler termination test waits for its first sample instead of
assuming Python installs signal handlers within 250 ms.

## Limits and submission gate

1. The pinned Linux builder and deployed GitHub Actions/Cloudflare combination
   still require a hosted acceptance run. Native macOS verification does not
   establish that production deployment works.
2. Ensembl filename checks reject a different named assembly, but cannot prove
   accession revisions when upstream reuses the same assembly filename.
3. Status reconstruction searches at most 300 recent runs. An old job with no
   remaining release and no discoverable run still cannot be classified
   reliably. Durable status storage remains a separate improvement.
4. Existing product limits remain: temporary packages above approximately
   1.9 GiB are not published, and no new authentication/challenge requirement
   has been added. This audit is not an exhaustive public-service abuse review.
5. Before freezing the software release for the manuscript, deploy the reviewed
   revision and record hosted acceptance for NCBI, a non-vertebrate Ensembl
   source, and an uploaded FASTA, including installation and sequence checks
   on the resulting package.
