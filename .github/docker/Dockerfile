FROM ghcr.io/johnnychen1113/autobsgenome-builder@sha256:17163ade2f837065af6790ed231dab16c0226c964b7a093a0fcca568c57f328d AS previous-builder

FROM rocker/r-ver:4.4.0

# System dependencies — zlib1g-dev is needed by XVector and Rhtslib
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    curl \
    unzip \
    python3 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update -qq && apt-get install -y gh && rm -rf /var/lib/apt/lists/*

# Preserve the exact faToTwoBit binary from builder v1.0.0. The upstream
# rolling binary changed, so copying from the immutable image avoids an
# unrelated converter upgrade in this release.
COPY --from=previous-builder /usr/local/bin/faToTwoBit /usr/local/bin/faToTwoBit
RUN echo "01f8c5a6900c88febf33e3b4cb4a8ee56bf3446e76784fce5ba00a1abd1d42a6  /usr/local/bin/faToTwoBit" \
        | sha256sum --check --status \
    && chmod +x /usr/local/bin/faToTwoBit

# Install a fixed NCBI Datasets release and verify the official release asset.
RUN curl -fsSL \
        https://github.com/ncbi/datasets/releases/download/v18.36.0/linux-amd64.cli.package.zip \
        -o /tmp/ncbi-datasets.zip \
    && echo "32003304f61e70ebeb58b09a69ea1cef6f4f159683ced7eba063fcb8bb16f0ea  /tmp/ncbi-datasets.zip" \
        | sha256sum --check --status \
    && unzip -jo /tmp/ncbi-datasets.zip datasets -d /usr/local/bin \
    && rm -f /tmp/ncbi-datasets.zip \
    && chmod +x /usr/local/bin/datasets \
    && datasets version | grep -F "datasets version: 18.36.0"

# Install R packages — update matrixStats first (>= 1.4.1 required by MatrixGenerics)
RUN Rscript -e ' \
    install.packages("matrixStats", repos = "https://cloud.r-project.org"); \
    install.packages("BiocManager", repos = "https://cloud.r-project.org"); \
    BiocManager::install(c("BSgenome", "BSgenomeForge"), update = FALSE, ask = FALSE) \
'

# Verify
RUN Rscript -e 'library(BSgenome); library(BSgenomeForge); cat("OK\n")'
