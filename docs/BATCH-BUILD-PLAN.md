# Batch Build Plan: All NCBI RefSeq Reference Genomes

## Scope

Build BSgenome packages for **all 10,177 NCBI RefSeq reference genomes** (excluding 9 already on Bioconductor).

## Numbers

| Group | Count | Typical Size |
|-------|-------|-------------|
| Bacteria | 8,959 | 1-15 MB |
| Archaea | 381 | 1-10 MB |
| Fungi | 321 | 10-100 MB |
| Invertebrate | 127 | 50-500 MB |
| Vertebrate (other) | 111 | 500 MB-3 GB |
| Plant | 107 | 100 MB-15 GB |
| Protozoa | 95 | 10-100 MB |
| Vertebrate (mammalian) | 76 | 1.5-3.5 GB |

Total genome data: ~537 GB
Estimated .tar.gz packages: ~134 GB (4:1 compression via 2bit)

## Priority Order

1. Vertebrate mammals (76) — most demand from TSSr/ChIP-seq users
2. Vertebrate other (111) — zebrafish, chicken, frog, etc.
3. Plants (107) — crops, model plants
4. Invertebrate (127) — insects, worms, etc.
5. Fungi (321)
6. Protozoa (95)
7. Archaea (381)
8. Bacteria (8,959) — smallest genomes, fastest builds

Within each group: smallest genome first (faster builds = faster progress).

## Rate Limiting

- **5 builds per batch, every 2 hours** = 60 builds/day
- **Estimated completion: ~170 days** (~6 months)
- All builds queue behind user-triggered builds (user builds always have priority)
- Concurrency: 1 build at a time (GitHub Actions concurrency group)

## How to Start

```bash
# 1. Generate the queue
python3 scripts/generate-build-queue.py scripts/build-queue.json

# 2. Upload queue to gh-pages branch
git checkout gh-pages
cp ../scripts/build-queue.json .
git add build-queue.json
git commit -m "Add build queue with 10177 reference genomes"
git push origin gh-pages
git checkout main

# 3. Trigger first batch manually
gh workflow run batch-build.yml --repo JohnnyChen1113/autoBSgenome

# 4. After that, the schedule runs automatically every 2 hours
```

## How to Pause

Set the cron schedule to a past date or delete the workflow file. Existing builds will complete but no new batches will start.

## How to Monitor

```bash
# Check queue status
curl -s https://johnnychen1113.github.io/autoBSgenome/build-queue.json | \
  python3 -c "import json,sys; q=json.load(sys.stdin); \
  print(f'Pending: {sum(1 for i in q if i[\"status\"]==\"pending\")}'); \
  print(f'Building: {sum(1 for i in q if i[\"status\"]==\"building\")}'); \
  print(f'Done: {sum(1 for i in q if i[\"status\"]==\"done\")}')"

# Check recent batch builds
gh run list --repo JohnnyChen1113/autoBSgenome --workflow batch-build.yml --limit 5
```

## Storage Strategy

- GitHub Releases: permanent storage for published packages (no size limit)
- GitHub Pages: PACKAGES index + browse page
- Large genomes (>1 GB packages): still use GitHub Releases, but may need to monitor total release count

## Safety

- batch-build.yml has `concurrency: bsgenome-batch` — only 1 batch job at a time
- build-bsgenome.yml has `concurrency: bsgenome-build` — only 1 actual build at a time
- User-triggered builds share the same build concurrency group → batch yields to users
- If queue is empty, batch job exits cleanly
