#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
METADATA_FILE="${REPO_ROOT}/reproducibility/builder-image.env"

source "$METADATA_FILE"
IMAGE_REF="${BUILDER_IMAGE}@${BUILDER_DIGEST}"

if [[ "${1:-}" != "--inside-container" ]]; then
  command -v docker >/dev/null
  mkdir -p "${REPO_ROOT}/reproduced"

  docker pull "$IMAGE_REF"
  docker run --rm \
    --platform linux/amd64 \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --env REPRO_OUTPUT_DIR=/workspace/reproduced \
    --volume "${REPO_ROOT}:/workspace" \
    --workdir /workspace \
    "$IMAGE_REF" \
    bash scripts/reproduce-test-build.sh --inside-container
  exit 0
fi

EXPECTED_BSGENOME=1.74.0
EXPECTED_BSGENOMEFORGE=1.6.0
EXPECTED_DATASETS=18.22.1
EXPECTED_DATASETS_SHA256=5d69784b20a518097c622879c6a2f2d1ff712b8c2178a439c5ff9fb02cca80c4
EXPECTED_FATOTWOBIT_SHA256=01f8c5a6900c88febf33e3b4cb4a8ee56bf3446e76784fce5ba00a1abd1d42a6

Rscript -e "
  stopifnot(getRversion() == '4.4.0')
  stopifnot(as.character(BiocManager::version()) == '3.20')
  stopifnot(as.character(packageVersion('BSgenome')) == '${EXPECTED_BSGENOME}')
  stopifnot(as.character(packageVersion('BSgenomeForge')) == '${EXPECTED_BSGENOMEFORGE}')
"

datasets version | grep -F "datasets version: ${EXPECTED_DATASETS}"
echo "${EXPECTED_DATASETS_SHA256}  /usr/local/bin/datasets" | sha256sum --check --status
echo "${EXPECTED_FATOTWOBIT_SHA256}  /usr/local/bin/faToTwoBit" | sha256sum --check --status

PACKAGE=BSgenome.Aluchuensis.NCBI.IFO4308
INPUT_FASTA=/workspace/test_data/GCF_016861625.1_AkawachiiIFO4308_assembly01_genomic.fna
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

cp "$INPUT_FASTA" "${WORK_DIR}/genome.fa"
cd "$WORK_DIR"

python3 /workspace/scripts/validate_fasta.py genome.fa --json fasta-validation.json
faToTwoBit genome.fa genome.2bit

cat > "${PACKAGE}.seed" <<SEED
Package: ${PACKAGE}
Title: Full genome sequences for Akawachii luchuensis
Description: Full genome sequences for Akawachii luchuensis as provided by NCBI for assembly IFO4308 and stored in Biostrings objects.
Version: 1.0.0
organism: Akawachii luchuensis
common_name: Akawachii luchuensis
genome: IFO4308
provider: NCBI
release_date: Aug. 2025
source_url: https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_016861625.1/
organism_biocview: Akawachii_luchuensis
BSgenomeObjname: Aluchuensis
circ_seqs: character(0)
seqs_srcdir: ${WORK_DIR}
seqfile_name: genome.2bit
SEED

Rscript -e "
  suppressPackageStartupMessages(library(BSgenome))
  suppressPackageStartupMessages(library(BSgenomeForge))
  forgeBSgenomeDataPkg('${PACKAGE}.seed')
"

R_BUILD_TAR=tar R CMD build --no-manual --no-build-vignettes "$PACKAGE"
TARBALL=$(find . -maxdepth 1 -name "${PACKAGE}_*.tar.gz" -print -quit)
test -n "$TARBALL"

mkdir -p library
R CMD INSTALL --library=library "$TARBALL"

R_LIBS_USER="${WORK_DIR}/library" Rscript -e "
  suppressPackageStartupMessages(library('${PACKAGE}', character.only = TRUE))
  stopifnot(inherits(Aluchuensis, 'BSgenome'))
  stopifnot(length(seqnames(Aluchuensis)) > 0L)
  first_seq <- seqnames(Aluchuensis)[1]
  width <- min(50L, seqlengths(Aluchuensis)[first_seq])
  retrieved <- getSeq(Aluchuensis, first_seq, start = 1L, end = width)
  stopifnot(inherits(retrieved, 'DNAString'))
  stopifnot(length(retrieved) == width, nchar(retrieved) == width)
  cat('first_sequence=', first_seq, '\n', sep = '')
  cat('retrieved_bases=', as.character(retrieved), '\n', sep = '')
" | tee sequence-check.txt

mkdir -p "$REPRO_OUTPUT_DIR"
cp "$TARBALL" "$REPRO_OUTPUT_DIR/"
cp fasta-validation.json sequence-check.txt "$REPRO_OUTPUT_DIR/"

OUTPUT_TARBALL="${REPRO_OUTPUT_DIR}/$(basename "$TARBALL")"
{
  echo "builder_version=${BUILDER_VERSION}"
  echo "builder_image=${IMAGE_REF}"
  echo "input_fasta_sha256=$(sha256sum "$INPUT_FASTA" | awk '{print $1}')"
  echo "output_tarball=$(basename "$OUTPUT_TARBALL")"
  echo "output_tarball_sha256=$(sha256sum "$OUTPUT_TARBALL" | awk '{print $1}')"
  echo "BSgenome=${EXPECTED_BSGENOME}"
  echo "BSgenomeForge=${EXPECTED_BSGENOMEFORGE}"
  echo "NCBI_Datasets=${EXPECTED_DATASETS}"
  echo "faToTwoBit_sha256=${EXPECTED_FATOTWOBIT_SHA256}"
} > "${REPRO_OUTPUT_DIR}/build-manifest.txt"

echo "Reproduced package written to ${OUTPUT_TARBALL}"
sha256sum "$OUTPUT_TARBALL"
