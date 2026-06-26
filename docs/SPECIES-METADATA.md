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
- `species-images/`: locally cached species images. Only URLs that pass a
  probe are downloaded, and the metadata points at these local copies instead
  of hotlinking upstream images.

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
  --image-probe-limit 1000 \
  --download-images \
  --image-dir species-images \
  --image-base-url https://johnnychen1113.github.io/autoBSgenome/species-images \
  --image-download-limit 1000 \
  --image-workers 8 \
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
- Ensembl species images are cached locally only after a successful image URL
  probe. Missing upstream images are not guessed client-side, so package cards
  do not flash a placeholder and then disappear.

Image caching is intentionally incremental. Many catalog organisms, especially
bacteria and viruses, do not have stable upstream images. Caching only confirmed
images avoids broken cards and keeps the public repository from growing
unnecessarily. The generator probes common model organisms first, then built
animal/plant/fungal entries, then the wider catalog. Image probing and
downloads use a small worker pool so high-volume cache runs can finish without
requiring thousands of serial network timeouts.
