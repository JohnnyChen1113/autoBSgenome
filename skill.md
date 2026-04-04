---
name: autobsgenome
description: Build and install BSgenome R packages for any organism. Use when user needs a BSgenome package, mentions genome sequences for R/Bioconductor, or references TSSr, motifmatchr, ChIPseeker, or similar tools that require BSgenome.
---

# AutoBSgenome — Build BSgenome R Packages

Build BSgenome R packages for any organism using the AutoBSgenome web service. No local R setup required.

## When to Use

Use this skill when the user:
- Needs a BSgenome package for a specific organism
- Is getting errors like "Requested genome is not installed"
- Wants to use TSSr, motifmatchr, ChIPseeker, Gviz, or other BSgenome-dependent tools
- Asks about genome packages for non-model organisms
- Needs to install a custom reference genome in R/Bioconductor

## Quick Check: Is it Already Available?

Before building, check if the package already exists:

```r
# Check Bioconductor
BiocManager::available("BSgenome")

# Check AutoBSgenome community repository
available.packages(repos = "https://johnnychen1113.github.io/autoBSgenome")
```

Or browse: https://johnnychen1113.github.io/autoBSgenome

## Build via API

### Step 1: Trigger Build

```bash
curl -s -X POST https://autobsgenome-api.dailylifecjh.workers.dev/api/build \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "BSgenome.ORGANISM.PROVIDER.ASSEMBLY",
    "organism": "Genus species",
    "accession": "GCF_XXXXXXXXX.X",
    "data_source": "ncbi",
    "version": "1.0.0",
    "circ_seqs": "MT"
  }'
```

Replace:
- `ORGANISM`: abbreviated (e.g., `Hsapiens`)
- `PROVIDER`: `NCBI` or `Ensembl`
- `ASSEMBLY`: assembly name without dots (e.g., `GRCh38`)
- `accession`: NCBI GCF_/GCA_ accession
- `circ_seqs`: circular sequences (e.g., `MT`, `character(0)` if none)

Response: `{"job_id": "xxx", "status": "queued"}`

### Step 2: Poll for Completion

```bash
curl -s https://autobsgenome-api.dailylifecjh.workers.dev/api/status/JOB_ID
```

Response when done:
```json
{
  "status": "complete",
  "download_url": "https://github.com/.../BSgenome.xxx.tar.gz",
  "file_name": "BSgenome.xxx_1.0.0.tar.gz"
}
```

Poll every 10 seconds. Typical build time: 45s–5min depending on genome size.

### Step 3: Install in R

```r
install.packages("DOWNLOAD_URL", repos = NULL, type = "source")
```

Or from the community repository (if published):
```r
install.packages("PACKAGE_NAME",
  repos = "https://johnnychen1113.github.io/autoBSgenome")
```

## Example: Build BSgenome for Aspergillus luchuensis

```bash
# Trigger
RESULT=$(curl -s -X POST https://autobsgenome-api.dailylifecjh.workers.dev/api/build \
  -H "Content-Type: application/json" \
  -d '{"package_name":"BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308","organism":"Aspergillus luchuensis","accession":"GCF_016861625.1","data_source":"ncbi","version":"1.0.0","circ_seqs":"character(0)"}')
JOB_ID=$(echo $RESULT | python3 -c "import json,sys;print(json.load(sys.stdin)['job_id'])")

# Wait for completion
while true; do
  STATUS=$(curl -s "https://autobsgenome-api.dailylifecjh.workers.dev/api/status/$JOB_ID")
  echo $STATUS | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['status'])"
  echo $STATUS | python3 -c "import json,sys;d=json.load(sys.stdin);exit(0 if d['status'] in ('complete','failed') else 1)" && break
  sleep 10
done

# Get download URL
URL=$(echo $STATUS | python3 -c "import json,sys;print(json.load(sys.stdin).get('download_url',''))")
```

Then in R:
```r
install.packages("URL_FROM_ABOVE", repos = NULL, type = "source")
library(BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308)
```

## Finding the Right Accession

If the user provides an organism name but not an accession:
1. Search NCBI: `https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{organism}/dataset_report`
2. Look for `refseq_category: "reference genome"` entries
3. Use the `accession` field (GCF_ preferred over GCA_)

## Web Interface

Users can also build packages at: https://autobsgenome.pages.dev
- Paste NCBI accession or Ensembl URL
- Auto-fills all metadata
- Download .tar.gz in under 1 minute
