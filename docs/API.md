# AutoBSgenome Web API

Base URL: `https://autobsgenome-api.dailylifecjh.workers.dev`

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
| `release_date` | No | Assembly release date (e.g. `Feb. 2022`) |
| `title` | No | Package title (auto-generated if omitted) |
| `source_url` | No | URL to source data |

**Response (200):**

```json
{
  "job_id": "4c1e14f7",
  "status": "queued"
}
```

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
JOB=$(curl -s -X POST https://autobsgenome-api.dailylifecjh.workers.dev/api/build \
  -H "Content-Type: application/json" \
  -d '{"package_name":"BSgenome.Drerio.NCBI.GRCz11","organism":"Danio rerio","accession":"GCF_000002035.6","data_source":"ncbi","version":"1.0.0","circ_seqs":"MT"}')
JOB_ID=$(echo $JOB | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

# 2. Poll for completion
while true; do
  STATUS=$(curl -s "https://autobsgenome-api.dailylifecjh.workers.dev/api/status/$JOB_ID")
  echo "$STATUS"
  echo "$STATUS" | python3 -c "import json,sys; s=json.load(sys.stdin)['status']; exit(0 if s in ('complete','failed') else 1)" && break
  sleep 10
done

# 3. Download
URL=$(echo "$STATUS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('download_url',''))")
curl -L -o package.tar.gz "$URL"
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
- `https://autobsgenome.pages.dev`
- `*.autobsgenome.pages.dev` (preview deployments)
- `http://localhost:*` (development)

## Rate Limits

- Build triggers: limited by GitHub Actions concurrency (1 concurrent build per repo)
- Status checks: no limit (Cloudflare Workers)
- Packages are available for **14 days** after build, then automatically cleaned up
