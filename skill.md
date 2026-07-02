---
name: autobsgenome
description: Build and install BSgenome R packages for any organism. Use when user needs a BSgenome package, mentions genome sequences for R/Bioconductor, or references TSSr, motifmatchr, ChIPseeker, or similar tools that require BSgenome.
---

# AutoBSgenome — Build BSgenome R Packages

Build BSgenome R packages for any organism using the AutoBSgenome web service. No local R setup required.

API base for agents:

```text
https://autobsgenome-api.bioinfoark.workers.dev
```

## When to Use

Use this skill when the user:
- Needs a BSgenome package for a specific organism
- Is getting errors like "Requested genome is not installed"
- Wants to use TSSr, motifmatchr, ChIPseeker, Gviz, or other BSgenome-dependent tools
- Asks about genome packages for non-model organisms
- Needs to install a custom reference genome in R/Bioconductor

## Quick Check: Is it Already Available?

Before building, check if the package already exists:

1. Search the package browser: https://autobsgenome.org/packages
2. Prefer a Bioconductor-hosted package when the exact organism and assembly match.
3. Prefer an existing AutoBSgenome tarball when the package card matches the requested organism, assembly, and accession.
4. Build only when no matching package exists.

## Build via API

### Step 1: Trigger Build

```bash
curl -s -X POST https://autobsgenome-api.bioinfoark.workers.dev/api/build \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "BSgenome.ORGANISM.PROVIDER.ASSEMBLY",
    "organism": "Genus species",
    "genome": "AssemblyName",
    "provider": "NCBI",
    "accession": "GCF_XXXXXXXXX.X",
    "data_source": "ncbi",
    "version": "1.0.0",
    "circ_seqs": "MT",
    "source_url": "https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_XXXXXXXXX.X/"
  }'
```

Replace:
- `ORGANISM`: abbreviated (e.g., `Hsapiens`)
- `PROVIDER`: `NCBI` or `Ensembl`
- `ASSEMBLY`: assembly name without dots (e.g., `GRCh38`)
- `accession`: NCBI GCF_/GCA_ accession
- `circ_seqs`: circular sequences (e.g., `MT`, `character(0)` if none)

Response includes `job_id`, queue status, and `delete_token`. Keep `delete_token` private.

### Step 2: Poll for Completion

```bash
curl -s https://autobsgenome-api.bioinfoark.workers.dev/api/status/JOB_ID
```

Response when done:
```json
{
  "status": "complete",
  "download_url": "https://github.com/.../BSgenome.xxx.tar.gz",
  "file_name": "BSgenome.xxx_1.0.0.tar.gz",
  "published": false,
  "total_seconds": 226
}
```

Poll every 5-10 seconds. Status responses may include `build_steps` with live step timings and `workflow_run_url`.

### Step 3: Install in R

```r
url <- "DOWNLOAD_URL"
pkg <- tempfile(fileext = ".tar.gz")
download.file(url, pkg, mode = "wb", method = "libcurl")
install.packages(pkg, repos = NULL, type = "source")
unlink(pkg)
```

Download AutoBSgenome tarballs to a local temporary file before calling
`install.packages()`. Do not pass remote URLs directly to `install.packages()`,
and do not use old CRAN-like repository install snippets.

### Optional: Delete a Temporary Build

Temporary builds are cleaned up automatically after two days. If the user asks to delete the current build earlier:

```bash
curl -s -X DELETE https://autobsgenome-api.bioinfoark.workers.dev/api/build/JOB_ID \
  -H "Content-Type: application/json" \
  -d '{"delete_token":"DELETE_TOKEN_FROM_BUILD_RESPONSE"}'
```

### Permanent Repository Inclusion

Do not publish user-triggered builds to the permanent community repository.
The public AutoBSgenome package index is maintainer-curated to avoid incorrect
metadata or user-supplied packages being mistaken for verified reference
packages. Return the temporary tarball download URL and direct R install command
instead.

## Example: Build BSgenome for Aspergillus luchuensis

```bash
# Trigger
RESULT=$(curl -s -X POST https://autobsgenome-api.bioinfoark.workers.dev/api/build \
  -H "Content-Type: application/json" \
  -d '{"package_name":"BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308","organism":"Aspergillus luchuensis","genome":"AkawachiiIFO4308","provider":"NCBI","accession":"GCF_016861625.1","data_source":"ncbi","version":"1.0.0","circ_seqs":"character(0)"}')
JOB_ID=$(echo $RESULT | python3 -c "import json,sys;print(json.load(sys.stdin)['job_id'])")
DELETE_TOKEN=$(echo $RESULT | python3 -c "import json,sys;print(json.load(sys.stdin)['delete_token'])")

# Wait for completion
while true; do
  STATUS=$(curl -s "https://autobsgenome-api.bioinfoark.workers.dev/api/status/$JOB_ID")
  echo $STATUS | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['status'])"
  echo $STATUS | python3 -c "import json,sys;d=json.load(sys.stdin);exit(0 if d['status'] in ('complete','failed') else 1)" && break
  sleep 10
done

# Get download URL
URL=$(echo $STATUS | python3 -c "import json,sys;print(json.load(sys.stdin).get('download_url',''))")
```

Then in R:
```r
url <- "URL_FROM_ABOVE"
pkg <- tempfile(fileext = ".tar.gz")
download.file(url, pkg, mode = "wb", method = "libcurl")
install.packages(pkg, repos = NULL, type = "source")
unlink(pkg)
library(BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308)
```

## Finding the Right Accession

If the user provides an organism name but not an accession:
1. Search NCBI: `https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{organism}/dataset_report`
2. Look for `refseq_category: "reference genome"` entries
3. Use the `accession` field (GCF_ preferred over GCA_)

## FASTA URL or Local FASTA Upload

The web/API supports user-provided nucleotide FASTA sources:

- FASTA URL builds: pass `fasta_source: "url"` and `fasta_url`.
- Local browser uploads: create a multipart session with `POST /api/uploads`, upload parts, complete the upload, then build with `fasta_source: "upload"` and `fasta_upload_url`.
- Supported filenames end in `.fa`, `.fasta`, `.fna`, or `.fas`, optionally with `.gz`.
- Protein FASTA extensions such as `.faa`, `.pep`, and `.aa` are rejected.
- Browser upload limit is 4 GB.

Do not publish user-supplied FASTA builds. Return the temporary tarball
download URL and tell the user to contact the AutoBSgenome maintainers if they
want a package reviewed for permanent index inclusion.

## Web Interface

Users can also build packages at: https://autobsgenome.org
- Paste NCBI accession or Ensembl URL
- Auto-fills all metadata
- Or provide a FASTA URL / local nucleotide FASTA upload
- Download the temporary `.tar.gz` or delete it early
