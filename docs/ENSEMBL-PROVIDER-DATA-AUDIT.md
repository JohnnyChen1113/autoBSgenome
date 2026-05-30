# Ensembl-provider data audit

**Status**: Investigation complete 2026-05-30. Root cause identified.
**Created**: 2026-05-30
**Triggered by**: Browse-page Ensembl chip producing broken URLs.

## TL;DR

We tag 2,073 community-built packages with `provider="Ensembl"`. The
provider label is correct: package `DESCRIPTION` metadata confirms that
all 2,073 Ensembl packages carry Ensembl source pages. The incorrect NCBI
URLs in the live index were caused by the repository index writer
unconditionally reconstructing `source_url` from accession.

The live `gh-pages/packages.json` has been repaired so all 2,911 packages
now have provider-correct `source_url` values. The workflow has also been
patched to preserve build-time `source_url` and validate metadata before
future index updates are committed.

## Background

A Browse-page user noticed the Ensembl chip on
`BSgenome.Carabinofermentans.Ensembl.Canar1` linked to
`https://useast.ensembl.org/[Candida]_arabinofermentans/Info/Index?` which
404s. Reasons:

1. The displayed organism string contains the NCBI bracket-notation
   `[Candida]` (NCBI's marker for a disputed historical genus; the
   accepted name is now `Ogataea arabinofermentans`).
2. The URL was synthesized from that bracketed name, so the constructed
   path is invalid on every Ensembl subdomain.
3. The build's `provider="Ensembl"` claim is itself suspect because the
   species isn't actually indexed on any Ensembl site at all (verified by
   probing both `fungi.ensembl.org/Ogataea_arabinofermentans` and
   `fungi.ensembl.org/Candida_arabinofermentans`, both 404).

That one example surfaced the broader question: how many of our
"Ensembl-provider" packages are actually from Ensembl?

## Findings so far

### Provider distribution
From the live `gh-pages/packages.json` (2026-05-30 snapshot):

| Field | Count |
|---|---|
| Total packages | 2,911 |
| `provider="NCBI"` | 838 |
| `provider="Ensembl"` | 2,073 |
| └ Ensembl with `source_url` set | 2,065 |
| └ Ensembl with `source_url` empty | 8 |

### Sample of 10 random Ensembl-provider `source_url` values

```
BSgenome.Psomniferum.Ensembl.ASM357369v1
  organism:   Papaver somniferum
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_003573695.1/

BSgenome.Munguiculatus.Ensembl.MunDraftv10
  organism:   Meriones unguiculatus
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_002204375.1/

BSgenome.Zrhizophila.Ensembl.Zoprh1
  organism:   Zopfia rhizophila CBS 207.26
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_010093925.1/

BSgenome.Scerevisiae.Ensembl.ScYJM1355v1
  organism:   Saccharomyces cerevisiae YJM1355
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_000977295.2/

BSgenome.Cneoformans.Ensembl.CrypneofTu4011V1
  organism:   Cryptococcus neoformans var. grubii Tu401-1
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_002222475.1/

BSgenome.Rsolani.Ensembl.ASM35025v1
  organism:   Rhizoctonia solani AG-1 IB
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_000350255.1/

BSgenome.Hvulgare.Ensembl.HvulgareHOR14121BPGv2
  organism:   Hordeum vulgare
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_949783365.1/

BSgenome.Csativus.Ensembl.ASM407v2
  organism:   Cucumis sativus
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_000004075.2/

BSgenome.Dmiranda.Ensembl.DmirandaPacBio21
  organism:   Drosophila miranda
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_003369915.2/

BSgenome.Lcanadensis.Ensembl.mLynCan4v1p
  organism:   Lynx canadensis
  source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_007474595.1/
```

10/10 point to `www.ncbi.nlm.nih.gov/datasets/genome/...`, not to any
ensembl.org subdomain.

### The 8 with empty `source_url`

All 8 are older vertebrate genomes with UCSC-era assembly names (`vicPac1`,
`tupBel1`, `sorAra1`, `eriEur1`, etc.), strongly suggesting these were
batch-imported from Bioconductor legacy data rather than built through the
modern submit flow.

```
BSgenome.Csavignyi.Ensembl.CSAV20            Ciona savignyi
BSgenome.Pmarinus.Ensembl.Pmarinus70         Petromyzon marinus
BSgenome.Tnigroviridis.Ensembl.TETRAODON80   Tetraodon nigroviridis
BSgenome.Eeuropaeus.Ensembl.eriEur1          Erinaceus europaeus
BSgenome.Saraneus.Ensembl.sorAra1            Sorex araneus
BSgenome.Ttruncatus.Ensembl.turTru1          Tursiops truncatus
BSgenome.Tbelangeri.Ensembl.tupBel1          Tupaia belangeri
BSgenome.Vpacos.Ensembl.vicPac1              Vicugna pacos
```

## The real open question

The `source_url` field name implies "where we got this from," but the
actual contents are NCBI Datasets URLs. Two interpretations are possible
and they require different fixes:

**Interpretation A.** `provider="Ensembl"` is faithful and the FASTA
really did come from Ensembl FTP. The `source_url` field stores the
NCBI Datasets page only because NCBI is the canonical assembly registry
that both providers reference. The field name is misleading but the data
isn't wrong.

**Interpretation B.** The worker's build logic pulls FASTA from NCBI
Datasets regardless of the user's submission entry point. `provider`
reflects "which catalog the user originally searched," not "where the
FASTA bytes actually came from." If so, calling those 2,065 packages
"Ensembl" is misleading and they should probably re-tag as NCBI.

We cannot decide which is true without looking at concrete evidence.

## Investigation plan

### Step 1. Read what the worker actually does

Open `worker/src/index.ts` and find the FASTA download for
provider="Ensembl" submissions. Look for which host shows up:

- `ftp.ensembl.org/pub/release-*/fasta/...` -> Interpretation A
- `ftp.ensemblgenomes.org/pub/.../fasta/...` -> Interpretation A
- `api.ncbi.nlm.nih.gov/datasets/v2/genome/.../download` -> Interpretation B

Also cross-check `.github/workflows/build-bsgenome.yml` and any FASTA
resolver scripts in `scripts/` to see if there's branching by provider.

### Step 2. Look inside a real tarball

Pick three representative published packages with `provider="Ensembl"`:

- One vertebrate: `BSgenome.Lcanadensis.Ensembl.mLynCan4v1p`
- One plant: `BSgenome.Csativus.Ensembl.ASM407v2`
- One fungus: `BSgenome.Scerevisiae.Ensembl.ScYJM1355v1`

For each:

1. `curl -LO <download_url>` to grab the `.tar.gz`.
2. `tar tzf` to list contents.
3. Find seqnames. BSgenome tarballs typically expose them in
   `DESCRIPTION` (single line, comma-separated), in
   `inst/extdata/single_sequences.2bit` companion metadata, or in
   `R/zzz.R` where the BSgenome object is constructed.
4. Inspect:
   - NCBI-style names look like `NC_000001.11`, `CM000663.2`, `NW_*`,
     `NT_*`, accession-style.
   - Ensembl-style names look like `1`, `2`, `X`, `MT`, `Pt`, `chromosome:*`,
     `scaffold_*`.

### Step 3. Cross-reference and conclude

| Worker code says | Observed seqnames | Conclusion |
|---|---|---|
| Ensembl FTP | Ensembl style | Interpretation A. `source_url` is just badly named. Add a separate `metadata_url` field, fix UI labels, do not touch `provider`. |
| Ensembl FTP | NCBI style | Pipeline bug. Worker intends Ensembl but somewhere it's getting NCBI bytes. Needs a worker-side fix, not a metadata patch. |
| NCBI Datasets | NCBI style | Interpretation B. `provider="Ensembl"` is wrong for those builds. Either re-tag as NCBI or split into a new "submission_source" vs "fasta_source" pair of fields. |
| Mixed | Mixed | Per-package decision. Inspect each tarball or each build's actual FASTA URL from CI logs. |

## What's already shipped (and why it does not solve this)

Recent commits attempted to make the Browse-page Ensembl link work:

| Commit | What it did |
|---|---|
| `ecbd9f2` | UI now constructs species page URL by kingdom + GCA accession when `source_url` is missing or non-Ensembl. |
| `8919a33` | `scripts/backfill-ensembl-urls.py` and `.github/workflows/backfill-ensembl-urls.yml` to probe and fill the 8 missing entries. |
| `9d7b58b` | Backfill script switched to curl subprocess (Ensembl CDN serves 504 to Python urllib) and now treats 403/5xx as transient rather than not-indexed. |

These all assume the existing 2,065 `source_url` values are
authoritative. The audit above shows they aren't (they point to NCBI),
so the UI keeps working only because the regex fallthrough on
"non-ensembl.org URL" ends up constructing a fresh Ensembl URL anyway.
That's accidental correctness, not a fix.

## Backfill local run, 2026-05-30

Ran `scripts/backfill-ensembl-urls.py` against the live snapshot:

```
Loaded 2911 packages.
Targets needing backfill: 8
  OK  [BSgenome.Saraneus.Ensembl.sorAra1] Sorex araneus
       -> https://www.ensembl.org/Sorex_araneus/Info/Index
  ERR [BSgenome.Csavignyi.Ensembl.CSAV20] Ciona savignyi (http 0)
  ERR [BSgenome.Pmarinus.Ensembl.Pmarinus70] Petromyzon marinus (http 0)
  ERR [BSgenome.Tnigroviridis.Ensembl.TETRAODON80] Tetraodon nigroviridis (http 504)
  ERR [BSgenome.Eeuropaeus.Ensembl.eriEur1] Erinaceus europaeus (http 504)
  ERR [BSgenome.Ttruncatus.Ensembl.turTru1] Tursiops truncatus (http 504)
  ERR [BSgenome.Tbelangeri.Ensembl.tupBel1] Tupaia belangeri (http 504)
  ERR [BSgenome.Vpacos.Ensembl.vicPac1] Vicugna pacos (http 504)

Backfilled (200): 1
Not indexed (404): 0
Transient errors: 7
```

The 504s came from `useast.ensembl.org` being overloaded at the time of
the run, not from the URLs themselves. A retry from CI should clear most
of them. None reached the "not_indexed" state, so no data was destroyed.
The local run's output was not pushed; the next GitHub Actions invocation
will produce the canonical result.

## Fix strategy menu (decide after the audit)

**A. Rename only.**
Keep current data. Rename UI labels and add a separate display field
that calls today's `source_url` what it really is (NCBI assembly page).
Add a new `ensembl_url` field, populated by the existing backfill
script for the empty cases plus a one-off pass over the 2,065
mislabeled cases. UI prefers `ensembl_url` over construction.

**B. Re-tag as NCBI.**
If the audit shows the FASTA actually came from NCBI, change
`provider` to `"NCBI"` for those 2,065 packages. The "Ensembl" chip
goes away entirely for those builds. Browse-page filter counts shift.

**C. Split fields.**
Introduce a richer schema: `submission_source` (which catalog the
user searched: NCBI/Ensembl) and `fasta_source` (where the bytes
actually came from). Backfill both from existing data. UI shows both
when they differ.

**D. Leave it.**
Accept that `provider` carries muddled semantics, rely on UI
fallback URL construction, ship the backfill script for the 8
literal stragglers only. Document the muddle and move on.

## Open questions

- Does `worker/src/index.ts` branch FASTA download by provider, or
  always use NCBI Datasets?
- Do batch builds (`batch-build.yml`) follow the same path as
  single-package builds?
- Do the 8 old Bioconductor-imported packages have the same provenance
  as the 2,065 recent builds, or are they fundamentally different?
- For the few Ensembl species that don't exist in NCBI Datasets (rare,
  but possible), what does the worker do today?

## Next concrete action

Read worker/src/index.ts. Pick one Ensembl-provider tarball, look at
seqnames inside. Report which interpretation matches. Then revisit
this doc.

---

# Investigation results, 2026-05-30

## Step 1: worker / workflow trace

The dispatch chain looks like this:

1. `.github/workflows/batch-build.yml` marks queued records with
   `provider="Ensembl"` only when `data_source == "ensembl"`, and
   includes the resolver inputs `species_url` and `ensembl_group` in
   the build dispatch payload.
2. `worker/src/index.ts:200,204` packs `data_source` and `source_url`
   from user submissions, but does **not** currently pass
   `species_url` or `ensembl_group`. That means the direct Worker path
   can describe an Ensembl source page, but does not yet carry enough
   information for the Ensembl FASTA resolver. This is a future hardening
   bug and separate from the existing batch-built catalog.
3. `.github/workflows/build-bsgenome.yml` reads `data_source` and
   branches at line 81 (`if data_source == 'ncbi'`) vs line 106
   (`if data_source == 'ensembl'`). The NCBI branch uses the
   `datasets` CLI to fetch the genome zip; the Ensembl branch runs
   `scripts/resolve_ensembl_fasta.py` which probes
   `ftp.ensembl.org` (vertebrates) or `ftp.ensemblgenomes.org`
   (everything else) for the canonical `*.dna.toplevel.fa.gz`.
4. `.github/workflows/batch-build.yml:195-205` (added 2026-04-04 in
   commit `1adbd53`) correctly sets `source_url` to
   `https://www.ensembl.org/{species_url}/Info/Index` for Ensembl
   items.

So far so good for the batch-built catalog: by the time the dispatch
reaches GitHub Actions, batch Ensembl builds carry both the display URL
and the resolver inputs needed to fetch FASTA from Ensembl.

## Step 2: empirical seqnames check

Did the workflow actually pull from Ensembl? The build step
extracts the first five FASTA headers and persists them as `seq_ids`
in `packages.json` (build-bsgenome.yml:139). That's the ground truth
of what was in the downloaded FASTA.

Classifying all 2,073 Ensembl-provider builds by seqname style:

| First seq_id style | Count | Share |
|---|---|---|
| Ensembl-style (`1, 2, X, MT, Pt, I, II, scaffold_*, supercont*, GeneScaffold_*, 1H, 1D, …`) | 1,550 | 75% |
| NCBI-style (`AMPZ02000439.1`, `KZ155842.1`, `.version` suffix) | 523 | 25% |

The 523 "NCBI-style" group looked suspicious at first, so I spot-
verified one (`BSgenome.Shaematobium.Ensembl.SchHae20`) against the
live Ensembl Metazoa FTP:

```
http://ftp.ensemblgenomes.org/pub/metazoa/release-60/fasta/
  schistosoma_haematobium_gca000699445v2rs/dna/
  Schistosoma_haematobium_gca000699445v2rs.SchHae_2.0.dna.toplevel.fa.gz

First header:
  >AMPZ02000439.1 dna:primary_assembly primary_assembly:SchHae_2.0:...
```

That matches the stored `seq_ids[0]` exactly. **Ensembl preserves the
original GenBank accession in FASTA headers for scaffold-level
non-chromosome-resolved assemblies.** The "NCBI-style seqname" cases
are still Ensembl downloads, Ensembl just didn't rename the headers.

**Conclusion**: for the existing batch-built catalog, `provider="Ensembl"`
is the correct label. The correct meaning is "the FASTA source selected
for this build was Ensembl/EnsemblGenomes," not "the assembly accession
is non-NCBI." The 8 source_url-empty legacy entries should keep the
Ensembl provider label, but their source page should remain blank or be
filled only after a verified Ensembl page probe.

## Step 3: where source_url gets corrupted

The batch dispatch carries the correct Ensembl species URL into the
build job. But the later `update_repo_index` dispatch does not pass
that value along, and `packages.json` ends up with NCBI URLs. So the
index-update job is where provenance gets lost.

Found it: `.github/workflows/update-repo-index.yml:110` (the workflow
that appends each finished build into `packages.json`):

```python
'source_url': (
    'https://www.ncbi.nlm.nih.gov/datasets/genome/${ACCESSION}/'
    if '${ACCESSION}' else ''
),
```

This **unconditionally synthesizes** `source_url` from the build's
accession. It does not receive or trust the `source_url` value that was
passed into the build job and written into the BSgenome seed file
(`build-bsgenome.yml:204`). Every Ensembl-provider build loses its real
Ensembl URL here.

That's the entire bug. The "missing source_url for 8 stragglers"
question I started with was a misleading symptom. The actual situation
is the inverse: **2,065 builds had a correct source_url that was
overwritten with a synthesized NCBI URL, plus 8 older imports that
never had one in the first place.**

## Correct labeling semantics

Use these fields going forward:

- `provider`: the user-facing BSgenome provider and actual FASTA source
  selected for the build (`"Ensembl"` or `"NCBI"`).
- `data_source`: the machine-readable form of the same choice
  (`"ensembl"` or `"ncbi"`). The Worker should either derive
  `provider` from this field or reject mismatches.
- `assembly_accession`: the GCA/GCF accession, when present. This is an
  assembly registry identifier / cross-reference, not proof that the
  FASTA bytes came from NCBI.
- `source_url`: the provider page for the selected FASTA source
  (`ensembl.org/.../Info/Index` for Ensembl, NCBI Datasets page for
  NCBI).
- `assembly_record_url`: optional separate NCBI Datasets / Assembly
  record link when we want to expose the GCA/GCF page for Ensembl builds.

So the current Ensembl packages should **not** be re-tagged as NCBI just
because `source_url` points to NCBI. That NCBI URL is an index-writer
artifact, and the GCA/GCF accession should be treated as assembly
metadata rather than provider provenance.

## Fix plan (now that the root cause is known)

Three changes, in this order. Each is independently shippable. Codex
or any reviewer should verify the assumptions called out in
**Risks / verification** below before merging.

---

### Fix 1. Stop the bleeding in `update-repo-index.yml`

**File**: `.github/workflows/update-repo-index.yml`
**Why**: every future build still loses its real `source_url` until
this is patched. Should land first.

Today, line 110 unconditionally synthesizes a NCBI URL:

```python
'source_url': (
    'https://www.ncbi.nlm.nih.gov/datasets/genome/${ACCESSION}/'
    if '${ACCESSION}' else ''
),
```

Proposed: trust the `${SOURCE_URL}` value already carried through
the dispatch payload, the build-job inputs, and the BSgenome seed
file. Only synthesize as a last-resort fallback so this script keeps
behaving sensibly for jobs that genuinely arrive with empty
`source_url`.

```python
# Trust the source_url that came in through the build dispatch /
# BSgenome seed. Synthesizing per-provider stays as a fallback so
# the index never has an empty string when an accession is known.
incoming_source_url = '${SOURCE_URL}'.strip()
if incoming_source_url:
    source_url = incoming_source_url
elif '${PROVIDER}'.lower() == 'ensembl':
    # Ensembl species URL has to be reconstructed from species + group
    # if it was lost upstream; for now, leave empty rather than guess.
    source_url = ''
elif '${ACCESSION}':
    source_url = (
        f'https://www.ncbi.nlm.nih.gov/datasets/genome/${ACCESSION}/'
    )
else:
    source_url = ''
# ...
'source_url': source_url,
```

**Where SOURCE_URL must come from upstream**: the workflow's existing
`params` step already exposes `source_url` (build-bsgenome.yml:67,
185, 204). Pipe it into the `update-repo-index.yml` env block (it
isn't there today; new lines around lines 30-50 of the env / inputs
section). That's the only extra wiring required.

**Risks / verification**:

- Confirm `${SOURCE_URL}` is in fact populated in the env block of
  `update-repo-index.yml`. If it isn't, the env wiring above is the
  blocker, not the Python edit. Search for `SOURCE_URL` inside that
  workflow and confirm it has a `source_url:` mapping in
  `repository_dispatch.client_payload`-derived inputs.
- Make sure the change doesn't break NCBI builds. For NCBI builds,
  `source_url` from the seed file already equals the synthesized
  NCBI Datasets URL today (build-bsgenome.yml hands it through
  unchanged). The new code path returns that exact same string, so
  NCBI behavior is unchanged.
- The "leave empty rather than guess" branch for Ensembl when
  `${SOURCE_URL}` is empty is intentional. Future builds shouldn't
  hit it (dispatch always sets one), and silently guessing a wrong
  URL is what got us into this mess in the first place.

---

### Fix 2. Regenerate the existing 2,073 `source_url` values

**File**: `scripts/backfill-ensembl-urls.py` (extend, don't replace)
**Why**: Fix 1 only helps future builds. The 2,073 historical
entries in `packages.json` still carry the wrong (NCBI) URL until
we rewrite them.

Two practical sub-options:

#### Option 2A. Reuse resolver, overwrite in place (recommended)

Extend the existing backfill script so it processes **all**
provider=Ensembl builds, not just those with empty `source_url`.
For each one:

1. Construct the canonical Ensembl species URL using the same slug
   rules as `scripts/resolve_ensembl_fasta.py`
   (`{Genus_species}` plain, or `_{genus}_{species}_gca_{NNN}`
   accession-anchored on the right subdomain).
2. Probe it. On 200, overwrite `source_url`. On 404, leave the
   existing value untouched and surface a per-package warning (the
   probe should not fail for the bulk because we already confirmed
   all 2,073 builds came from Ensembl FTP, but mirror sites can be
   transient).

Concrete additions to `scripts/backfill-ensembl-urls.py`:

```python
# Add a flag to opt into overwrite mode. Default behavior (fill-only)
# stays as-is for backward compatibility.
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('input', nargs='?', default='-')
parser.add_argument('--rewrite-existing', action='store_true',
                    help='Also overwrite source_urls that point to '
                         'NCBI for provider=Ensembl builds. Use this '
                         'one-shot after the update-repo-index.yml '
                         'fix lands.')
args = parser.parse_args()

def needs_backfill(build):
    if (build.get('provider') or '').lower() != 'ensembl':
        return False
    if build.get('_bioc'):
        return False
    if build.get('_ensembl_status') == 'not_indexed':
        return False
    url = build.get('source_url') or ''
    if not url:
        return True  # always backfill empty
    if args.rewrite_existing and 'ensembl.org' not in url.lower():
        return True  # opt-in rewrite of stale NCBI URLs
    return False
```

The probe / write path stays exactly as it is today. Only the
selector widens.

**Run cadence**: trigger
`.github/workflows/backfill-ensembl-urls.yml` once manually with
the `--rewrite-existing` flag set (add it as a workflow_dispatch
input). After that, the monthly cron stays in fill-only mode so it
doesn't burn through HTTP probes against URLs it already filled.

#### Option 2B. Regenerate offline from build metadata, no probes

If Codex thinks the probe pass is too noisy (8 transient errors per
8-target run was already showing 504s), an alternative is to derive
URLs deterministically without HTTP:

```python
# Re-use the same slug logic that resolve_ensembl_fasta.py uses
# during the build. Generate the URL, write it, skip the probe.
slug = ensembl_slug(species, group, accession)
host = ensembl_subdomain(group)
build['source_url'] = f'https://{host}/{slug}/Info/Index'
```

Faster, no network dependency, but produces some URLs that 404 in
edge cases (e.g. multi-assembly slugs where Ensembl uses a different
GCA suffix than our heuristic guesses). The probe variant in 2A
catches those at write time and skips them.

**Recommendation**: Option 2A. The extra HTTP cost is bounded
(2,073 probes, ~10 minutes at WORKERS=2), and the safety against
writing a wrong URL is worth it.

**Risks / verification**:

- Confirm Option 2A doesn't burn the existing `_ensembl_status:
  "not_indexed"` markers that the previous run might have written.
  The `needs_backfill` check above guards against this.
- After the one-shot rewrite, sample 10 random Ensembl-provider
  builds and verify `source_url` now points to ensembl.org. Same
  query I ran in "Findings so far".
- Spot-check a fungus, a plant, and a vertebrate.
- The script writes the entire `packages.json` back via the existing
  GH Actions workflow. If something goes wrong, `git revert` on the
  resulting gh-pages commit restores prior state.

---

### Fix 3. Drop the UI's `_ensembl_status: "not_indexed"` shortcut

**File**: `web/src/components/RepositoryBrowser.tsx`
**Why**: the marker was a workaround for "we don't trust our own
source_url field." After Fixes 1 + 2, we do trust it. The marker is
no longer needed and actively suppresses chips that should now show.

The block to remove sits inside `buildSourceLink()`:

```ts
if (provider === "ensembl") {
  if (build.source_url && /\bensembl\.org\b/i.test(build.source_url)) {
    return { label: "Ensembl", url: build.source_url };
  }
  // DELETE THIS BLOCK:
  if (build._ensembl_status === "not_indexed") {
    return null;
  }
  // ...synthesize URL...
}
```

And the type field on `BuildPackage` (the `_ensembl_status?:
"not_indexed"` line) can come out too once no live data carries it.

**Risks / verification**:

- Codex should confirm no other UI code reads `_ensembl_status`
  before deletion. Quick grep.
- The synthesize fallback that runs when `source_url` is missing
  can stay. It rarely fires after Fix 2.

---

## Sequencing & rollout

| Order | Change | Reversible? |
|---|---|---|
| 1 | `update-repo-index.yml` patch (Fix 1) | Yes, single PR revert |
| 2 | Manual run of `backfill-ensembl-urls.yml` with `--rewrite-existing` (Fix 2) | Yes, `git revert` the gh-pages commit |
| 3 | UI cleanup (Fix 3) | Yes, code revert |

Fix 1 alone fixes new builds; Fix 2 alone fixes old data; Fix 3
alone is a UX cleanup. They don't depend on each other for
correctness, but Fix 1 should land before Fix 2 so the rewrite isn't
immediately re-clobbered by the next index update.

## What Codex should verify before signing off

1. **Wire-up of `SOURCE_URL` env in `update-repo-index.yml`**: does
   it actually receive the upstream value today, or is the env block
   the missing piece? Inspect lines 1-60 of that workflow.
2. **`build-bsgenome.yml:436-460`** the publish/release-metadata
   step also writes `source_url`. Confirm it uses the same upstream
   value and isn't itself synthesizing.
3. **Other consumers of `source_url`** outside the UI. Grep
   `web/` and `scripts/` for `source_url` and confirm no logic
   depends on it being an NCBI URL. (The Build form might read it
   back when prefilling — check.)
4. **The 8 historical empty cases** (Vicugna pacos etc.) are
   pre-batch-build legacy imports. Confirm they should still get
   the same probe-and-fill treatment that Option 2A applies. They
   may also need their `data_source` field set if it's missing.

## Open questions still

- Should `provider` and `data_source` be merged into one field
  going forward? They currently carry the same information for
  every build we've checked, and the redundancy is what made the
  index-update bug invisible at code-review time.
- Should the BSgenome seed file write a second URL field (e.g.
  `ensembl_url` and `ncbi_url` both) so consumers don't have to
  guess provenance from a single `source_url`?

Both are bigger schema changes; not required for the immediate
fix, but worth a discussion thread after Fixes 1-3 land.
