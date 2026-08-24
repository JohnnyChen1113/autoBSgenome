FROM ghcr.io/johnnychen1113/autobsgenome-builder@sha256:17163ade2f837065af6790ed231dab16c0226c964b7a093a0fcca568c57f328d

# Builder v1.1.0 is an incremental tool release. Inheriting from the immutable
# v1.0.0 image keeps R, Bioconductor, BSgenome, BSgenomeForge, system libraries,
# GitHub CLI, and faToTwoBit unchanged.
RUN echo "01f8c5a6900c88febf33e3b4cb4a8ee56bf3446e76784fce5ba00a1abd1d42a6  /usr/local/bin/faToTwoBit" \
        | sha256sum --check --status

# Install a fixed NCBI Datasets release and verify the official release asset.
RUN curl -fsSL \
        https://github.com/ncbi/datasets/releases/download/v18.36.0/linux-amd64.cli.package.zip \
        -o /tmp/ncbi-datasets.zip \
    && echo "32003304f61e70ebeb58b09a69ea1cef6f4f159683ced7eba063fcb8bb16f0ea  /tmp/ncbi-datasets.zip" \
        | sha256sum --check --status \
    && unzip -jo /tmp/ncbi-datasets.zip datasets -d /usr/local/bin \
    && rm -f /tmp/ncbi-datasets.zip \
    && chmod +x /usr/local/bin/datasets \
    && echo "2240faf73ca17f56f25d8009f5d50c76a7d77883a78f0287d990b417a23bf393  /usr/local/bin/datasets" \
        | sha256sum --check --status \
    && datasets version | grep -F "datasets version: 18.36.0"

# Verify that the inherited biological build stack did not drift.
RUN Rscript -e " \
    stopifnot(getRversion() == '4.4.0'); \
    stopifnot(as.character(BiocManager::version()) == '3.20'); \
    stopifnot(as.character(packageVersion('BSgenome')) == '1.74.0'); \
    stopifnot(as.character(packageVersion('BSgenomeForge')) == '1.6.0'); \
    library(BSgenome); library(BSgenomeForge); cat('OK\n') \
"
