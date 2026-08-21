# Curated BSgenome Catalog — Roadmap

## Core Principles

1. **Temporary public builds** — website and public API builds expire after 2 days
2. **Maintainer-curated catalog** — only the scheduled maintainer workflow can add reviewed official-source packages
3. **GitHub Releases and Zenodo storage** — storage is selected by artifact size without Git bloat
4. **PACKAGES index on gh-pages** — standard CRAN-like format for curated packages
5. **Browseable frontend** — https://autobsgenome.org/packages with search and organism taxonomy

## Architecture

```
Website/API request → temporary GitHub Release (build-{jobId}, 2-day TTL)

Maintainer batch selection → build with internal publish_to_index flag
  → curated GitHub Release or Zenodo record
  → packages.json and PACKAGES regenerated on gh-pages
  → package appears in the public catalog
```

## Phase 1: Curated Catalog Pipeline

- [x] Restrict permanent index updates to the maintainer batch workflow
- [x] Keep website and public API builds temporary
- [x] Update `packages.json` and `PACKAGES` from curated build events
- [x] Render the catalog from `packages.json`
- [ ] Include existing Bioconductor BSgenome packages as external links

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
