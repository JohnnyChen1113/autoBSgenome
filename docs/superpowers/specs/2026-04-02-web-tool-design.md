# AutoBSgenome Web — Design Spec

## Goal

A zero-cost web tool that builds BSgenome R packages from an NCBI accession or custom FASTA. Users paste an accession, review auto-filled metadata, and download a ready-to-install package.

## Architecture

```
Cloudflare Pages (frontend) → Cloudflare Workers (API proxy) → GitHub Actions (R build) → GitHub Releases (package hosting)
```

All free-tier. No paid services.

## User Flow

### Step 1: Input
- Text field: NCBI accession (GCF_/GCA_) or URL
- "Fetch" button calls NCBI Datasets API v2 directly from browser (CORS supported)
- Alternative: drag-and-drop FASTA upload (for custom genomes)

### Step 2: Review
- Auto-filled form from NCBI API response:
  - Package name: `BSgenome.{AbbrevOrganism}.{Provider}.{Assembly}`
  - Organism, Common name, Assembly, Provider, Release date, Version (1.0.0)
  - circ_seqs: auto-detected from NCBI sequence_reports API (`assigned_molecule_location_type`)
  - Title/Description: auto-generated from BSgenome convention (in Advanced accordion)
- FASTA source toggle: "Use official from NCBI" (default) / "Upload my own"
- All fields editable
- "Build BSgenome Package" button

### Step 3: Build Progress
- Worker receives metadata, triggers GitHub Actions via `repository_dispatch`
- Frontend polls for build status
- Show progress steps: Downloading FASTA → Converting to 2bit → Building R package → Uploading

### Step 4: Result
- Download .tar.gz button
- Copy-able `install.packages()` command (direct URL)
- Copy-able repo install command (temporary repo, 14-day TTL)
- Info box: "Available for 14 days"

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js + React + Tailwind CSS 4 + shadcn/ui |
| Design | SLU academic theme (Source Serif 4 / Inter / JetBrains Mono, #003DA5 primary) |
| API proxy | Cloudflare Workers (~100 lines: hide GitHub PAT, dispatch Actions, proxy status) |
| Build | GitHub Actions (ubuntu-latest, R + faToTwoBit + BSgenomeForge) |
| Storage | GitHub Releases (packages + PACKAGES index, 14-day cleanup via scheduled Action) |
| Deploy | Cloudflare Pages (free) |

## NCBI API Integration

Two API calls (no auth, free):
1. `GET https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{ACC}/dataset_report` → organism, assembly name, release date, common name
2. `GET https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{ACC}/sequence_reports` → circular sequence detection via `assigned_molecule_location_type`

URL parsing regex: `(GC[AF]_\d{9}\.\d+)` to extract accession from various NCBI URL formats.

## Package Name Generation

From NCBI metadata:
- Part 1: `BSgenome` (fixed)
- Part 2: First letter of genus (uppercase) + full species name (lowercase), e.g. `Hsapiens`
- Part 3: Provider — `NCBI` (from accession type)
- Part 4: Assembly name, e.g. `GRCh38`

## Title/Description Convention

- **Title**: `Full genome sequences for {Organism} ({Provider} version {Assembly})`
- **Description**: `Full genome sequences for {Organism} ({Common name}) as provided by {Provider} ({Assembly}, {Date}) and stored in Biostrings objects.`

## GitHub Actions Workflow

Triggered by `repository_dispatch` with `build_bsgenome` event type. Payload includes all metadata + job ID.

Steps:
1. Download FASTA from NCBI FTP (or from uploaded artifact)
2. Install faToTwoBit, convert FASTA → .2bit
3. Setup R + cache Bioconductor deps
4. Generate seed file + run forgeBSgenomeDataPkg + R CMD build
5. Upload .tar.gz as GitHub Release
6. Update PACKAGES index
7. Callback to Worker with result

Scheduled cleanup: weekly Action deletes releases older than 14 days.

## Scope for V1

**In scope:**
- NCBI accession auto-fill (GCF_/GCA_)
- Manual form entry as fallback
- Build via GitHub Actions
- Download + install commands
- Temporary repo (14 days)

**Out of scope (V2+):**
- Ensembl support
- Custom FASTA upload via R2
- Persistent community repository
- Build caching/deduplication
- i18n
