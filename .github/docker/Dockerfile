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

# Install faToTwoBit
RUN curl -sL https://hgdownload.cse.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit -o /usr/local/bin/faToTwoBit \
    && chmod +x /usr/local/bin/faToTwoBit

# Install NCBI datasets CLI
RUN curl -sL https://ftp.ncbi.nlm.nih.gov/pub/datasets/command-line/v2/linux-amd64/datasets -o /usr/local/bin/datasets \
    && chmod +x /usr/local/bin/datasets

# Install R packages — update matrixStats first (>= 1.4.1 required by MatrixGenerics)
RUN Rscript -e ' \
    install.packages("matrixStats", repos = "https://cloud.r-project.org"); \
    install.packages("BiocManager", repos = "https://cloud.r-project.org"); \
    BiocManager::install(c("BSgenome", "BSgenomeForge"), update = FALSE, ask = FALSE) \
'

# Verify
RUN Rscript -e 'library(BSgenome); library(BSgenomeForge); cat("OK\n")'
