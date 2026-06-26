# Species Metadata Shards

The package browser loads `packages.json`, `bioc-packages.json`, and
`catalog.json` as the authoritative package/catalog indexes. Rich organism
metadata is optional and lives in `species-metadata/` on the `gh-pages` branch.

## Files

- `species-metadata/index.json`: small manifest with shard names and counts.
- `species-metadata/A.json` ... `species-metadata/Z.json`: organism metadata
  keyed by normalized organism/scientific-name lookup strings.
- `species-metadata/_.json`: non-alphabetic fallback shard.
- `species-metadata/taxonomy-cache.json`: incremental NCBI Taxonomy API cache
  used by the generator workflow.

The frontend first loads `index.json`, then fetches only the shard needed for
the currently visible package results. This keeps the `/packages` first load
small while allowing the catalog to carry richer metadata.

## Generator

Run locally against a checked-out `gh-pages` tree:

```bash
python3 scripts/generate-species-metadata.py \
  --packages packages.json \
  --bioc-packages bioc-packages.json \
  --catalog catalog.json \
  --assembly-summary /tmp/assembly_summary_refseq.txt \
  --assembly-summary /tmp/assembly_summary_genbank.txt \
  --taxonomy-cache species-metadata/taxonomy-cache.json \
  --fetch-taxonomy \
  --fetch-limit 1000 \
  --probe-images \
  --image-probe-limit 100 \
  --out-dir species-metadata
```

The GitHub Actions workflow `.github/workflows/generate-species-metadata.yml`
runs the same command weekly and can also be started manually.

## Metadata Sources

- Existing package metadata supplies common names and taxonomy for built
  packages when already available.
- NCBI `assembly_summary_refseq.txt` and `assembly_summary_genbank.txt` supply
  `taxid`, `species_taxid`, assembly level, and release date for catalog
  entries.
- NCBI Datasets Taxonomy API fills taxonomy and common-name fields
  incrementally, bounded by `fetch_limit`.
- Ensembl species images are written only after a successful image URL probe.
  The browser also hides failed images, so missing upstream images do not create
  broken cards.
