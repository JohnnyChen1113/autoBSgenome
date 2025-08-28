# autoBSgenome

A user-friendly, interactive command-line tool for building R BSgenome packages. This script turns the complex process of creating a BSgenome package into a simple, guided questionnaire.

## Why use autoBSgenome?

While official tools like `BSgenomeForge` exist, `autoBSgenome` provides a smoother experience for certain use cases, especially when:
- Your source FASTA file contains ambiguous IUPAC nucleotide codes (e.g., N, Y, R, M).
- You need to build a package for a specific genome assembly version that may not be the absolute latest one on NCBI.

`autoBSgenome` is designed to be robust and forgiving, guiding you through the process from start to finish.

## Features

- **Interactive Wizard:** A step-by-step guided process for entering all the necessary metadata.
- **Flexible Navigation:** Made a mistake? No problem. You can type `back` at any prompt to return to the previous question and correct your input.
- **Automatic Dependency Checking:** The script automatically checks for required command-line tools (`faToTwoBit`) and R packages (`BSgenome`, `BSgenomeForge`) and will prompt you to install them if they are missing.
- **Generates All Necessary Files:** Automatically creates the `.seed` file and the `build.R` script required for the final package.

## Requirements

- Python 3.x
- An R environment

The script will handle the installation of all other Python and R package dependencies for you.

## Usage

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/JohnnyChen1113/autoBSgenome.git
    cd autoBSgenome
    ```

2.  **Make the script executable (optional but recommended):**
    ```bash
    chmod +x autoBSgenome.py
    ```

3.  **Run the script:**
    ```bash
    ./autoBSgenome.py
    ```

4.  **Follow the interactive prompts:**
    - The script will first check for all required dependencies and ask for permission to install any that are missing.
    - It will then guide you through entering the metadata for your BSgenome package.
    - At any point during metadata entry, you can type `back` to return to the previous question.
    - Once all information is gathered, the script will generate the necessary files and ask if you want to proceed with the build and installation.