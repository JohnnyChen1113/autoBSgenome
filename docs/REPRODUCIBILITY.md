# Reproducing the reference BSgenome build

The autoBSgenome reference build uses a public container with a fixed image digest. The digest identifies the complete builder environment and is used directly by the GitHub Actions package workflow.

## Run the reference build

From the repository root, run the following command.

```bash
./scripts/reproduce-test-build.sh
```

The script pulls the fixed `linux/amd64` builder image, validates the included *Akawachii luchuensis* FASTA file, converts it to UCSC 2bit, forges the BSgenome package, runs `R CMD build`, installs the source package and retrieves sequence from the installed BSgenome object.

Outputs are written to `reproduced/`.

- `BSgenome.Aluchuensis.NCBI.IFO4308_1.0.0.tar.gz`
- `fasta-validation.json`
- `sequence-check.txt`
- `build-manifest.txt`

## Builder identity

The fixed image metadata are stored in `reproducibility/builder-image.env`. Exact software versions and binary checksums are recorded in `reproducibility/builder-v1.0.0-versions.txt`.

The image can also be retrieved directly.

```bash
docker pull ghcr.io/johnnychen1113/autobsgenome-builder@sha256:17163ade2f837065af6790ed231dab16c0226c964b7a093a0fcca568c57f328d
```

UCSC faToTwoBit does not expose a version string. The release record therefore identifies the exact binary by its SHA256 checksum and ELF Build ID.
