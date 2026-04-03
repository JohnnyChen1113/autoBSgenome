# AutoBSgenome Paper Outline
## Target: NAR Genomics & Bioinformatics

### Title
AutoBSgenome: a zero-setup web tool for building BSgenome R packages from any genome assembly

### Authors
Junhao Chen, Zhenguo Lin*
Department of Biology, Saint Louis University, St. Louis, MO, USA

---

## Abstract (~150 words)
- Problem: BSgenome packages are essential for Bioconductor genome analysis but building custom ones requires complex toolchain
- Solution: AutoBSgenome — web tool that builds BSgenome packages from NCBI/Ensembl accessions in <1 minute
- Key features: auto-fill metadata, auto-detect circular sequences, zero local setup
- Architecture: serverless (Cloudflare + GitHub Actions), zero operating cost
- Availability: https://autobsgenome.pages.dev

## Introduction
1. BSgenome packages in the Bioconductor ecosystem — what they are, why they matter
2. The coverage gap — only ~30 model organisms have pre-built packages vs millions of sequenced genomes
3. Current building process — BSgenomeForge limitations, the 15-field metadata burden
4. Real user feedback — TSSr users requesting BSgenome removal because they can't build packages
5. Our solution — AutoBSgenome web tool

## Materials and Methods
1. **System architecture** — Cloudflare Pages (frontend) + Workers (API) + GitHub Actions (compute) + Releases (storage)
2. **Zero-cost design** — all services within free tiers, sustainable indefinitely
3. **Metadata auto-fill** — NCBI Datasets API v2, Ensembl REST API
4. **Circular sequence detection** — assigned_molecule_location_type from sequence reports
5. **Package building pipeline** — Docker image with R + BSgenomeForge + faToTwoBit, seed file generation, R CMD build
6. **BSgenome naming convention compliance** — auto-generated Title/Description following official patterns
7. **Input validation** — 4-part package name format checking

## Results
1. **Performance benchmarks** — build times for various genome sizes (fungal, plant, mammalian)
2. **Comparison with existing approaches** — AutoBSgenome vs BSgenomeForge CLI vs manual process
3. **Feature comparison table** — support for old assembly versions, IUPAC codes, non-registered organisms
4. **Case studies** — building BSgenome for organisms used in TSSr analyses
5. **Accessibility** — zero prerequisites vs the 5+ tools needed for manual building

## Discussion
1. Lowering barriers to BSgenome usage enables broader adoption of Bioconductor tools
2. Serverless architecture as a model for sustainable bioinformatics web tools
3. Limitations — large genomes, Ensembl FASTA naming variations, custom FASTA upload
4. Future directions — R-universe integration, community package registry, Bioconductor submission pipeline

## References (~25)
