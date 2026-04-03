# autoBSgenome

Build BSgenome R packages for any organism — via the **web** or the **command line**.

## Web Tool (New!)

**https://autobsgenome.pages.dev**

Build BSgenome packages directly in your browser. No local R, Python, or command-line tools required.

1. Paste an NCBI accession (GCF_/GCA_) or Ensembl species URL
2. Review the auto-filled metadata
3. Click Build — package is ready in under 1 minute
4. Download the `.tar.gz` and install with `R CMD INSTALL`

The web tool supports both NCBI and Ensembl as data sources, auto-detects circular sequences (mitochondria, chloroplast, plasmids), and generates Title/Description following BSgenome conventions.

**API available** — see [docs/API.md](docs/API.md) for programmatic access.

---

## CLI Tool

A user-friendly, interactive command-line tool for building R BSgenome packages. This script turns the complex process of creating a BSgenome package into a simple, guided questionnaire.

### Why use autoBSgenome?

While official tools like `BSgenomeForge` exist, `autoBSgenome` provides a smoother experience for certain use cases, especially when:
- Your source FASTA file contains ambiguous IUPAC nucleotide codes (e.g., N, Y, R, M).
- You need to build a package for a specific genome assembly version that may not be the absolute latest one on NCBI.

`autoBSgenome` is designed to be robust and forgiving, guiding you through the process from start to finish.

### Features

- **Interactive Wizard:** A step-by-step guided process for entering all the necessary metadata.
- **Flexible Navigation:** Made a mistake? No problem. You can type `back` at any prompt to return to the previous question and correct your input.
- **Automatic Dependency Checking:** The script automatically checks for required command-line tools (`faToTwoBit`) and R packages (`BSgenome`, `BSgenomeForge`) and will prompt you to install them if they are missing.
- **Generates All Necessary Files:** Automatically creates the `.seed` file and the `build.R` script required for the final package.

### Requirements

- Python 3.x
- An R environment

The script will handle the installation of all other Python and R package dependencies for you.

### Usage

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/JohnnyChen1113/autoBSgenome.git
    cd autoBSgenome
    ```

2.  **Run the script:**
    ```bash
    python autoBSgenome.py
    ```

3.  **Follow the interactive prompts:**
    - The script will first check for all required dependencies and ask for permission to install any that are missing.
    - It will then guide you through entering the metadata for your BSgenome package.
    - At any point during metadata entry, you can type `back` to return to the previous question.
    - Once all information is gathered, the script will generate the necessary files and ask if you want to proceed with the build and installation.

## Architecture (Web Tool)

```
Cloudflare Pages (frontend) → Cloudflare Workers (API) → GitHub Actions (R build) → GitHub Releases (packages)
```

All services run within free tiers. Zero operating cost.

## License

GPL-3.0
