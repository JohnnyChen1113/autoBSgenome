# BSgenome Community Repository — Roadmap

## Core Principles

1. **Opt-in publishing** — builds are temporary (14 days) by default; users choose to publish permanently
2. **GitHub Releases as storage** — unlimited total size, 2 GB per file, no Git bloat
3. **PACKAGES index on gh-pages** — standard CRAN-like format, R's `install.packages()` works natively
4. **Browseable frontend** — https://johnnychen1113.github.io/autoBSgenome with search and organism taxonomy

## Architecture

```
User builds BSgenome package
  ↓
Temporary: GitHub Release (build-{jobId}, 14-day TTL)
  ↓
User clicks "Publish to Repository"
  ↓
Permanent: GitHub Release (pkg-{packageName}, no TTL)
  + packages.json updated on gh-pages
  + PACKAGES index regenerated
  + Browseable on the repo frontend page
```

## Phase 1: User-Initiated Publishing (Current Priority)

- [ ] Add "Publish to Repository" button on result page
- [ ] Worker endpoint: `POST /api/publish` — copies temp release to permanent release
- [ ] GitHub Action or Worker: update `packages.json` and `PACKAGES` on gh-pages
- [ ] Frontend repo page reads `packages.json` and renders package list
- [ ] Include existing Bioconductor BSgenome packages as "external links" (not hosted, just discoverable)

## Phase 2: Bioconductor BSgenome Directory

- [ ] Scrape/list all existing BSgenome packages from Bioconductor (~226 entries)
- [ ] Add them to the browse page as "Available on Bioconductor" with install instructions
- [ ] Users see a unified view: community-built + officially available packages
- [ ] Prevents redundant builds for organisms that already have official packages

## Phase 3: Pre-built Popular Genomes

Long-term goal: pre-build all NCBI RefSeq representative genomes, prioritized by usage.

### Rate limiting strategy
- **10 builds per hour** via scheduled GitHub Action
- **Priority order:**
  1. Model organisms (human, mouse, rat, zebrafish, fly, worm, yeast, arabidopsis) — already on Bioconductor, link only
  2. Common research organisms with no BSgenome (from NCBI download stats)
  3. All RefSeq representative genomes, alphabetically

### Scheduled build workflow
```yaml
# .github/workflows/batch-build.yml
# Runs every hour, picks the next N unbuilt organisms from a queue
on:
  schedule:
    - cron: "0 * * * *"  # every hour
```

### Queue management
- `build-queue.json` in gh-pages: list of accessions to build, sorted by priority
- Each run picks the next 10, triggers builds, marks as done
- Queue populated from NCBI assembly_summary_refseq.txt

### Estimated timeline
- ~30,000 representative RefSeq genomes
- 10/hour × 24 hours = 240/day
- **~125 days to complete full coverage** (~4 months)

### Storage estimate
- Average BSgenome .tar.gz: ~50 MB (heavily skewed — bacteria <1 MB, mammals ~800 MB)
- 30,000 × 50 MB = ~1.5 TB
- GitHub Releases: no total limit, but consider Cloudflare R2 ($0.015/GB/month) for very large scale

## Phase 4: TSSHub Integration

- [ ] API endpoint for TSSHub to query available BSgenome packages
- [ ] TSSHub can show "BSgenome available" / "Build BSgenome" button per organism
- [ ] Deep linking: TSSHub → AutoBSgenome with pre-filled accession
