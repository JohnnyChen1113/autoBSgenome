# AutoBSgenome Web API

Base URL: `https://api.autobsgenome.org`

## Endpoints

### POST /api/build

Trigger a BSgenome package build.

**Request:**

```json
{
  "package_name": "BSgenome.Hsapiens.NCBI.GRCh38",
  "organism": "Homo sapiens",
  "common_name": "Human",
  "genome": "GRCh38",
  "provider": "NCBI",
  "version": "1.0.0",
  "circ_seqs": "MT",
  "accession": "GCF_000001405.40",
  "data_source": "ncbi",
  "release_date": "Feb. 2022",
  "title": "Full genome sequences for Homo sapiens (NCBI version GRCh38)",
  "source_url": "https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_000001405.40/"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `package_name` | Yes | 4-part name: `BSgenome.Organism.Provider.Assembly` |
| `organism` | Yes | Scientific name (e.g. `Homo sapiens`) |
| `common_name` | No | Common name (e.g. `Human`) |
| `genome` | No | Assembly name (e.g. `GRCh38`) |
| `provider` | No | Data provider (e.g. `NCBI`, `Ensembl`) |
| `version` | No | Package version (default: `1.0.0`) |
| `circ_seqs` | No | Circular sequences, comma-separated (e.g. `MT`) or `character(0)` |
| `accession` | No | NCBI accession (e.g. `GCF_000001405.40`) — used for FASTA download |
| `data_source` | No | `ncbi` or `ensembl` (default: `ncbi`) — determines FASTA download source |
| `fasta_source` | No | `url` to download a user-provided FASTA URL, `upload` to use a browser-uploaded FASTA; otherwise omitted or set by `data_source` |
| `fasta_url` | Only for URL builds | HTTP(S) URL for a `.fa`, `.fasta`, `.fna`, `.fas`, or gzip-compressed FASTA file |
| `fasta_upload_url` | Only for uploads | Signed `download_url` returned by `POST /api/uploads` |
| `fasta_file_name` | Only for uploads | Original uploaded FASTA filename |
| `fasta_file_size` | Only for uploads | Uploaded FASTA byte size |
| `release_date` | No | Assembly release date (e.g. `Feb. 2022`) |
| `title` | No | Package title (auto-generated if omitted) |
| `source_url` | No | URL to source data |

**Response (200):**

```json
{
  "job_id": "4c1e14f7",
  "status": "queued",
  "queue_position": 0,
  "delete_token": "hmac-token-for-this-job"
}
```

Keep `delete_token` private. It lets the original browser session delete the temporary GitHub Release for this build before the scheduled 2-day cleanup.

### DELETE /api/build/:jobId

Delete a temporary build release and its Git tag. This only applies to temporary `build-<jobId>` GitHub Releases; it does not delete packages already published to the permanent package repository.

**Request:**

```json
{
  "delete_token": "hmac-token-from-post-build"
}
```

**Response (200):**

```json
{
  "status": "deleted",
  "job_id": "4c1e14f7",
  "release_deleted": true,
  "tag_deleted": true
}
```

### FASTA URL builds

Use `fasta_source: "url"` when the FASTA file is hosted outside NCBI or Ensembl, for example on a lab server, ENA/JGI/UCSC download endpoint, Zenodo draft file, or an object-store signed URL.

```json
{
  "package_name": "BSgenome.Custom.URL.MyAssembly",
  "organism": "Custom organism",
  "genome": "MyAssembly",
  "provider": "URL",
  "version": "1.0.0",
  "circ_seqs": "character(0)",
  "data_source": "ncbi",
  "fasta_source": "url",
  "fasta_url": "https://example.org/path/genome.fa.gz",
  "source_url": "https://example.org/assembly-page"
}
```

The build workflow downloads `fasta_url` directly in GitHub Actions and does not echo the URL in logs. The final package is still delivered as a temporary public GitHub Release asset, so do not use private or sensitive sequence data unless public temporary artifacts are acceptable.

### POST /api/uploads

Create a signed upload URL for a user-provided FASTA file. The API stores the file in the `FASTA_UPLOADS` R2 bucket, then GitHub Actions downloads it during `/api/build`.

**Request:**

```json
{
  "file_name": "my-genome.fasta.gz",
  "file_size": 73400320,
  "content_type": "application/gzip"
}
```

**Response (200):**

```json
{
  "upload_id": "9ccfb9e2-0ab9-4a23-a9de-6f8fd4c67c0a",
  "file_name": "my-genome.fasta.gz",
  "file_size": 73400320,
  "upload_url": "https://api.autobsgenome.org/api/uploads/...",
  "download_url": "https://api.autobsgenome.org/api/uploads/...",
  "expires_at": "2026-06-25T18:00:00.000Z",
  "max_upload_bytes": 104857600
}
```

Upload the file with:

```bash
curl -X PUT --upload-file my-genome.fasta.gz "$UPLOAD_URL"
```

Then trigger a build with:

```json
{
  "package_name": "BSgenome.Custom.Upload.MyAssembly",
  "organism": "Custom organism",
  "genome": "MyAssembly",
  "provider": "Upload",
  "version": "1.0.0",
  "circ_seqs": "character(0)",
  "data_source": "ncbi",
  "fasta_source": "upload",
  "fasta_upload_url": "<download_url from /api/uploads>",
  "fasta_file_name": "my-genome.fasta.gz",
  "fasta_file_size": "73400320"
}
```

Supported file names end in `.fa`, `.fasta`, `.fna`, or `.fas`, optionally with `.gz`.
Browser uploads currently support files up to 100 MB because the file body passes through the Worker request. Use FASTA URL for larger files until multipart direct upload is implemented. Upload URLs expire after 2 days; successful builds delete the uploaded FASTA after GitHub Actions downloads it, and the R2 `uploads/` lifecycle rule removes abandoned uploads after 2 days. Uploaded FASTA builds produce temporary GitHub Release downloads only; they are not added to the public package repository or `packages.json`. Do not upload private or sensitive sequence data unless the deployment's artifact storage policy is appropriate for that data.

### GET /api/status/:jobId

Check build status.

**Response — building:**

```json
{
  "job_id": "4c1e14f7",
  "status": "building"
}
```

**Response — complete:**

```json
{
  "job_id": "4c1e14f7",
  "status": "complete",
  "package_name": "BSgenome.Hsapiens.NCBI.GRCh38 1.0.0",
  "download_url": "https://github.com/JohnnyChen1113/autoBSgenome/releases/download/build-4c1e14f7/BSgenome.Hsapiens.NCBI.GRCh38_1.0.0.tar.gz",
  "file_name": "BSgenome.Hsapiens.NCBI.GRCh38_1.0.0.tar.gz",
  "file_size": 782000000
}
```

**Response — failed:**

```json
{
  "job_id": "4c1e14f7",
  "status": "failed",
  "message": "BUILD_FAILED: ..."
}
```

## Usage Example (curl)

```bash
# 1. Trigger build
JOB=$(curl -s -X POST https://api.autobsgenome.org/api/build \
  -H "Content-Type: application/json" \
  -d '{"package_name":"BSgenome.Drerio.NCBI.GRCz11","organism":"Danio rerio","accession":"GCF_000002035.6","data_source":"ncbi","version":"1.0.0","circ_seqs":"MT"}')
JOB_ID=$(echo $JOB | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
DELETE_TOKEN=$(echo $JOB | python3 -c "import json,sys; print(json.load(sys.stdin)['delete_token'])")
echo "Job ID: $JOB_ID"

# 2. Poll for completion
while true; do
  STATUS=$(curl -s "https://api.autobsgenome.org/api/status/$JOB_ID")
  echo "$STATUS"
  echo "$STATUS" | python3 -c "import json,sys; s=json.load(sys.stdin)['status']; exit(0 if s in ('complete','failed') else 1)" && break
  sleep 10
done

# 3. Download
URL=$(echo "$STATUS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('download_url',''))")
curl -L -o package.tar.gz "$URL"

# Optional: delete the temporary public release before the 2-day cleanup
curl -X DELETE "https://api.autobsgenome.org/api/build/$JOB_ID" \
  -H "Content-Type: application/json" \
  -d "{\"delete_token\":\"$DELETE_TOKEN\"}"
```

## Usage Example (R)

```r
# After building via the web UI or API, install directly:
install.packages(
  "https://github.com/JohnnyChen1113/autoBSgenome/releases/download/build-XXXX/BSgenome.Organism.Provider.Assembly_1.0.0.tar.gz",
  repos = NULL, type = "source"
)
```

## CORS

The API allows requests from:
- `https://autobsgenome.org`
- `https://www.autobsgenome.org`
- `https://autobsgenome.pages.dev`
- `*.autobsgenome.pages.dev` (preview deployments)
- `http://localhost:*` (development)

## Rate Limits

- Build triggers: limited by GitHub Actions concurrency (1 concurrent build per repo)
- Status checks: no limit (Cloudflare Workers)
- Temporary packages are available for **2 days** after build, then automatically cleaned up
- Users can delete their current temporary build earlier with `DELETE /api/build/:jobId` when they still have the `delete_token` returned by `POST /api/build`
