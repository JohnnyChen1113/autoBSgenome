# autoBSgenome

Build BSgenome R packages for any organism — via the **web** or the **command line**.

## Web Tool

**https://autobsgenome.org**

Build BSgenome packages directly in your browser. No local R, Python, or command-line tools required.

1. Paste an NCBI accession (GCF_/GCA_) or Ensembl species URL
2. Or provide a FASTA download URL / local nucleotide FASTA upload
3. Review the auto-filled metadata
4. Click Build, then download the temporary `.tar.gz`
5. Copy the one-line R install command, which downloads the tarball to a temporary local file and installs it without remote-URL tar warnings

The web tool supports NCBI, Ensembl, user-provided FASTA URLs, and local FASTA uploads. It validates nucleotide FASTA inputs and generates Title/Description fields following BSgenome conventions. The public, server-hosted `.tar.gz` download is cleaned up automatically after approximately two days, so users should save a local copy when they need it later.

**API available** — see [docs/API.md](docs/API.md) for programmatic access.

**Agent Skill available** — use the installable
[`skills/autobsgenome`](skills/autobsgenome) folder, or fetch the same canonical
instructions from <https://autobsgenome.org/skill.md>.

---

## CLI Tool

The standalone CLI builds BSgenome packages on your own computer. Give it an
NCBI accession/URL or an official Ensembl species URL and it prefills the
interactive questionnaire with upstream metadata. Every value remains
editable. Other data sources use fully manual metadata entry.

### Why use autoBSgenome?

While official tools like `BSgenomeForge` exist, `autoBSgenome` provides a smoother experience for certain use cases, especially when:
- Your source FASTA file contains ambiguous IUPAC nucleotide codes (e.g., N, Y, R, M).
- You need to build a package for a specific genome assembly version that may not be the absolute latest one on NCBI.

`autoBSgenome` is designed to be robust and forgiving, guiding you through the process from start to finish.

### Features

- **Official metadata prefill:** Accepts NCBI `GCF_`/`GCA_` accessions and URLs,
  plus official Ensembl, Ensembl Plants, Fungi, Bacteria, Protists, and Metazoa
  species URLs.
- **Interactive Wizard:** Review each prefilled value, press Enter to accept it,
  or type a replacement.
- **Flexible Navigation:** Made a mistake? No problem. You can type `back` at any prompt to return to the previous question and correct your input.
- **FASTA choice:** Download the official NCBI/Ensembl FASTA or select a local
  `.fa`, `.fasta`, `.fna`, or gzip-compressed FASTA file.
- **Correct genome dates:** Automatic mode uses the upstream assembly release
  date, never the date on which the package is built.
- **Safe local build:** Work happens in an isolated temporary directory and
  stops immediately if conversion, forging, or `R CMD build` fails.

### Requirements

- Python 3.10 or newer; the CLI has no third-party Python dependencies
- R with the `BSgenome` and `BSgenomeForge` packages
- UCSC `faToTwoBit`

NCBI and Ensembl official FASTA downloads use Python's standard HTTPS support
and do not require an additional download tool. NCBI downloads are resolved
from `ftp.ncbi.nlm.nih.gov` over HTTPS and checked against the published MD5
when available. Missing system or R dependencies are reported with a clear
error; the CLI does not silently install binaries.

### Usage

1.  **Install the command:**
    ```bash
    git clone https://github.com/JohnnyChen1113/autoBSgenome.git
    cd autoBSgenome
    python -m pip install .
    ```

    The source remains a standalone file, so running it directly is also
    supported:

    ```bash
    python autoBSgenome.py GCF_003254395.2
    ```

2.  **Build from NCBI or Ensembl:**

    ```bash
    autobsgenome GCF_003254395.2
    autobsgenome https://fungi.ensembl.org/Aaosphaeria_arxii_cbs_175_79_gca_010015735/Info/Index
    ```

3.  **Or enter metadata manually:**

    ```bash
    autobsgenome --manual
    ```

Use `--no-install` to leave the completed source tarball in the current
directory without installing it into the local R library.

## Architecture (Web Tool)

```
Cloudflare Workers (frontend) → Cloudflare Workers (API) → GitHub Actions (R build) → GitHub Releases / package repository
```

The public package repository is indexed by `packages.json` and the R-facing `src/contrib/PACKAGES` file on the `gh-pages` branch.

## Reproducibility

The package build workflow uses a public builder image pinned by an immutable digest. A complete reference build can be run from the repository root with one command.

```bash
./scripts/reproduce-test-build.sh
```

The command rebuilds the included *Akawachii luchuensis* test package and verifies sequence retrieval from the installed BSgenome object. The fixed image identity, exact software versions and output files are described in [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## License

GPL-3.0
