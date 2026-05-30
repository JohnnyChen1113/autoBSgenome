# Package Metadata Contract

This contract prevents package provenance from being inferred differently
by different parts of the system.

## Required source semantics

`provider` and `source_url` must agree:

| Provider | Required `source_url` |
|---|---|
| `NCBI` | `https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_or_GCF.../` |
| `Ensembl` | `https://*.ensembl.org/.../Info/Index` |

`source_url` is the upstream source page for the genome data. It is not
the package download URL and not a fallback accession link.

`download_url` is the autoBSgenome-hosted package tarball.

NCBI packages must also carry the concrete `GCA_...` or `GCF_...`
`accession` used by `source_url`.

## Provenance metadata

Newly indexed packages must include a `provenance` object:

```json
{
  "schema_version": 1,
  "provider": "Ensembl",
  "source_url": "https://www.ensembl.org/Apteryx_haastii/Info/Index",
  "source_accession": "GCA_003342985.1",
  "built_at": "2026-05-30T12:00:00Z",
  "workflow_run_id": "123456789",
  "workflow_run_url": "https://github.com/JohnnyChen1113/autoBSgenome/actions/runs/123456789",
  "builder_image": "ghcr.io/johnnychen1113/autobsgenome-builder:latest",
  "package_sha256": "64-character sha256 hex digest",
  "description_sha256": "64-character sha256 hex digest"
}
```

Older packages may not have `provenance`, but every new package written by
`update-repo-index.yml` is required to have it.

## Validation

`scripts/validate-packages-metadata.py` enforces the contract. It is run:

- during `update-repo-index.yml` for the package currently being indexed;
- weekly by `validate-packages-metadata.yml` against the public gh-pages
  `packages.json`.

## Append-only ledger

Every future index update appends one JSON object to
`provenance/builds.jsonl` on `gh-pages`. `packages.json` remains the current
display index; `provenance/builds.jsonl` is the historical audit trail.
