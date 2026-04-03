# AutoBSgenome: a bridge infrastructure for converting public genome assemblies into Bioconductor-ready BSgenome packages

**Junhao Chen and Zhenguo Lin***

Department of Biology, Saint Louis University, St. Louis, MO 63103, USA

*Corresponding author: zhenguo.lin@slu.edu

---

## Abstract

BSgenome data packages provide standardized, memory-efficient access to reference genome sequences within the R/Bioconductor ecosystem and are required by a broad range of genome-aware analytical tools. Although more than one hundred BSgenome packages are available on Bioconductor, they cover only a limited subset of sequenced species, creating an adoption barrier for researchers working with non-model organisms. Constructing custom BSgenome packages requires specialized software, command-line expertise, and familiarity with multiple file formats — skills that many bench biologists lack. Here, we present AutoBSgenome, a web-based infrastructure that converts public genome assemblies into installable BSgenome packages through an accession-driven, fully automated workflow. Users provide an NCBI or Ensembl assembly accession; the system retrieves all metadata, detects circular sequences, and produces a standards-compliant BSgenome package. We benchmarked AutoBSgenome across 33 genomes spanning fungi, plants, and vertebrates, with median build times of 44 seconds for small genomes (<100 MB) and 2–5 minutes for vertebrate-scale genomes. In addition, we have initiated a systematic effort to pre-build BSgenome packages for all 10,177 NCBI RefSeq reference genomes, with completed packages hosted in a publicly accessible CRAN-like repository. AutoBSgenome operates on a zero-cost serverless architecture, ensuring long-term sustainability without dedicated infrastructure funding. By lowering the expertise barrier to standardized genome resource generation, AutoBSgenome broadens practical access to BSgenome-dependent Bioconductor workflows for the growing diversity of non-model organisms.

**Availability:** https://autobsgenome.pages.dev | Repository: https://johnnychen1113.github.io/autoBSgenome | Source: https://github.com/JohnnyChen1113/autoBSgenome

---

## Introduction

Reference genome sequences underpin nearly all modern genomic analyses, from transcription start site profiling to motif discovery, variant annotation, and chromatin analysis. Within the R/Bioconductor ecosystem, BSgenome packages serve as the standard representation for full genome sequences (Pages et al.; Huber et al. 2015). These packages encapsulate reference assemblies in a compact, memory-efficient format built on Biostrings objects, enabling lazy loading and seamless interoperability with a broad suite of downstream tools. Packages such as TSSr (Lu et al. 2021), motifmatchr, Gviz, GenomicFeatures (Lawrence et al. 2013), and ChIPseeker depend on BSgenome objects to retrieve sequence data, making BSgenome packages an essential gateway to genome-aware workflows in R.

Despite their central role, the availability of pre-built BSgenome packages is limited. Although Bioconductor hosts more than one hundred BSgenome data packages, these cover only a small subset of the rapidly growing diversity of publicly available genome assemblies (Sayers et al. 2023). Researchers studying non-model organisms — which now constitute the majority of active genome-scale investigations — must construct custom BSgenome packages before they can employ the analytical infrastructure that depends on them.

Constructing a custom BSgenome package, however, presents a substantial procedural barrier. The process requires a local R/Bioconductor environment, the UCSC faToTwoBit utility for FASTA-to-2bit conversion (Kent et al. 2002), and the BSgenomeForge package (Pages). Users must compose a seed file in Debian Control File (DCF) format containing 15 or more fields, adhering to a strict four-part naming convention (BSgenome.Organism.Provider.Assembly) and specific title/description wording conventions. Each step is prone to subtle errors — missing trailing newlines in the seed file, IUPAC ambiguity codes in the FASTA, platform-specific binary compatibility issues with faToTwoBit — that are difficult to diagnose for researchers whose primary expertise lies outside software engineering.

The BSgenomeForge package provides convenience functions such as `forgeBSgenomeDataPkgFromNCBI()` that automate portions of this workflow. In practice, however, these functions operate smoothly only for the approximately 50–60 organisms whose assemblies are registered in GenomeInfoDb (Lawrence et al. 2009). For unregistered organisms, the functions either fail or require manual specification of metadata and circular sequence information. Moreover, when assembly names map to multiple accession versions, the resolution is ambiguous, and older assembly versions cannot be readily targeted.

The practical consequences of this complexity are evident in real-world usage. Users of the TSSr package have repeatedly requested removal of the BSgenome dependency, not because the BSgenome framework is inadequate, but because constructing a custom package for their organism of interest proved prohibitively difficult. This feedback reveals a critical insight: the barrier to adoption lies not in the BSgenome infrastructure itself, but in the difficulty of generating BSgenome packages for organisms outside the narrow set of well-supported model species.

To address this accessibility gap, we developed AutoBSgenome, a web-based infrastructure that operationalizes BSgenome package generation as an accession-driven, fully automated service. AutoBSgenome does not replace BSgenomeForge at the algorithmic level; rather, it makes the entire package generation pipeline accessible to any researcher through a web interface, with no local software installation, no programming knowledge, and no familiarity with the underlying toolchain. In addition to on-demand builds, we have initiated a systematic effort to pre-build BSgenome packages for all NCBI RefSeq reference genomes and host them in a publicly browsable, CRAN-like repository.

## Materials and Methods

### System architecture

AutoBSgenome is implemented as a serverless web application composed of four components (Figure 1): a static frontend deployed on Cloudflare Pages, an API proxy on Cloudflare Workers, a containerized build pipeline on GitHub Actions, and package storage on GitHub Releases. All components operate within the free tiers of their respective platforms, ensuring zero ongoing infrastructure cost under the present deployment model.

The frontend is built with Next.js, Tailwind CSS, and shadcn/ui components, deployed as a static site with global content delivery. The API proxy (~100 lines of TypeScript) encapsulates authentication credentials and relays build requests. The build pipeline uses a pre-built Docker image (based on rocker/r-ver:4.4.0) containing R, BSgenome, BSgenomeForge, the faToTwoBit utility, and the NCBI Datasets CLI, eliminating dependency installation overhead on each build.

### Metadata retrieval and circular sequence detection

For NCBI assemblies, AutoBSgenome queries the NCBI Datasets API v2 (Cox et al. 2025). The `dataset_report` endpoint retrieves organism taxonomy, assembly name, release date, and provider information. The `sequence_reports` endpoint enumerates all sequences and identifies circular molecules by inspecting the `assigned_molecule_location_type` field, which reliably classifies mitochondria, chloroplasts, plasmids, apicoplasts, and kinetoplasts across all organisms — not only those registered in GenomeInfoDb. For Ensembl assemblies, the Ensembl REST API (Yates et al. 2015) provides equivalent metadata.

When a user provides a GenBank accession (GCA_) that lacks organelle annotations, AutoBSgenome detects this through absence of non-chromosomal entries in the sequence report and suggests the corresponding RefSeq accession (GCF_), which typically provides more complete circular sequence metadata. This cross-referencing is performed automatically using the `paired_accession` field from the dataset report.

### Package generation pipeline

The pipeline proceeds through five stages: (i) FASTA download from NCBI or Ensembl; (ii) conversion to UCSC 2bit format; (iii) seed file generation with validated metadata following BSgenome naming and description conventions; (iv) package forging via `forgeBSgenomeDataPkg()`; and (v) `R CMD build` to produce the installable tarball.

### Community repository

Completed packages are published to a CRAN-like repository hosted on GitHub Pages (https://johnnychen1113.github.io/autoBSgenome), enabling installation via the standard R `install.packages()` function. The repository maintains a machine-readable PACKAGES index and a browsable web interface organized by taxonomic group. Users may opt to publish their builds to this permanent repository; additionally, an automated batch pipeline systematically pre-builds packages for all NCBI RefSeq reference genomes at a rate of approximately 720 per day.

### Programmatic API

A REST API is provided for integration with automated workflows and AI-assisted coding tools. The API supports build triggering (`POST /api/build`), status polling (`GET /api/status/:jobId`), and queue inspection (`GET /api/queue`).

## Results

### Systematic benchmark across diverse genomes

To evaluate AutoBSgenome across a range of genome sizes and taxonomic groups, we built BSgenome packages for 33 organisms spanning fungi (12 species, 2.2–33 MB), plants and algae (11 species, 12.9–133.1 MB), and vertebrates (10 species, 366–674 MB) (Table 1). All builds used the pre-built Docker image with cached R dependencies.

**Table 1.** Benchmark results for BSgenome package construction across 33 organisms.

| Taxonomic group | Species tested | Genome size range | Median build time | Build success rate | Package size range |
|---|---|---|---|---|---|
| Fungi / Microsporidia | 12 | 2.2–33 MB | 44 s | 12/12 (100%) | 0.6–9.3 MB |
| Plants / Algae | 11 | 12.9–133.1 MB | 52 s | 11/11 (100%) | 3.5–34 MB |
| Vertebrates (fish) | 10 | 366–674 MB | 148 s | 10/10 (100%) | 122–173 MB |
| **Total** | **33** | **2.2–674 MB** | **52 s** | **33/33 (100%)** | **0.6–173 MB** |

Circular sequences were correctly detected in organisms with mitochondrial genomes (e.g., *Saccharomyces cerevisiae*, MT). For the GenBank accession GCA_000002035.4 (*Danio rerio*), which lacks organelle annotations, AutoBSgenome correctly identified the absence and suggested the corresponding RefSeq accession GCF_000002035.6, which includes mitochondrial sequence data.

All 33 generated packages were successfully installed in a clean R 4.4.0 session and verified to load correctly via `library()` and `seqnames()`.

### Comparison with existing approaches

We compared AutoBSgenome with manual BSgenome construction and the BSgenomeForge CLI across five representative organisms (Table 2), including both GenomeInfoDb-registered and unregistered species.

**Table 2.** Empirical comparison of BSgenome construction methods.

| Feature | Manual process | BSgenomeForge CLI | AutoBSgenome |
|---|---|---|---|
| Local R required | Yes | Yes | No |
| Additional tools needed | faToTwoBit, text editor | None | None |
| Metadata fields to fill | 15 (manual) | 2–5 (partial auto) | 0 (fully auto) |
| Non-registered organism | Full manual workflow | Requires organism + circ_seqs args | Fully automatic |
| Circular seq detection | Manual lookup | Auto (registered only) | Auto (all organisms) |
| Old assembly versions | Manual seed editing | Ambiguous name resolution | Direct accession |
| User steps | ~10 | ~3 | 3 clicks |
| Time to installable package | 30–60 min | 10–15 min | <1 min (median 52 s) |
| Programming required | Yes (R, shell) | Yes (R) | No |

### Community repository and batch pre-building

At the time of writing, AutoBSgenome hosts 33 pre-built BSgenome packages in its community repository, with an automated pipeline systematically building packages for all 10,177 NCBI RefSeq reference genomes. The repository is organized by taxonomic group and provides a searchable web interface. Packages can be installed directly from R:

```r
install.packages("BSgenome.Tflavidus.NCBI.ASM371156v2",
  repos = "https://johnnychen1113.github.io/autoBSgenome")
```

## Discussion

AutoBSgenome addresses a persistent accessibility gap in the Bioconductor ecosystem by providing bridge infrastructure between public genome assemblies and the standardized BSgenome representation that genome-aware analytical tools require. The significance of this work extends beyond convenience: by lowering the expertise barrier to BSgenome package generation, AutoBSgenome expands the practical reach of the entire Bioconductor genome analysis toolchain to the long tail of sequenced organisms.

The tool's design reflects a deliberate emphasis on accessibility over novelty at the algorithmic level. AutoBSgenome does not introduce new methods for genome representation or sequence analysis; rather, it operationalizes existing infrastructure — BSgenomeForge, faToTwoBit, NCBI Datasets API — into an accession-driven workflow that requires no local software, no command-line interaction, and no specialized knowledge. This approach addresses the observation that the primary barrier to BSgenome adoption is procedural rather than computational.

The zero-cost serverless architecture merits discussion as a deployment model for academic bioinformatics tools. The well-documented disappearance of published web tools — often within years of publication — is frequently attributable to unsustainable hosting costs (Wren 2017). By leveraging free-tier cloud services for all components, AutoBSgenome demonstrates that production-grade bioinformatics infrastructure can be deployed and maintained without dedicated funding, a consideration of particular relevance to resource-constrained research groups.

The systematic pre-building of BSgenome packages for all NCBI RefSeq reference genomes represents a further contribution. The resulting community repository provides a shared resource that eliminates redundant package construction across the research community. As this collection grows, it has the potential to serve as the largest unofficial repository of BSgenome packages, complementing the curated packages maintained by the Bioconductor project.

Several limitations should be noted. Very large genomes exceeding approximately 10 GB may approach the six-hour timeout imposed by GitHub Actions, although such genomes are uncommon outside polyploid plant species. Ensembl FASTA filename patterns exhibit occasional variation across species, which may cause retrieval failures; these are addressed as reported. The current implementation does not support user-provided FASTA files, limiting use to genomes available through NCBI or Ensembl. Finally, the sustainability of the zero-cost model depends on continued availability of free-tier allocations from the hosting providers, though we note that these have been stable for multiple years.

Future development priorities include an interactive taxonomy browser for the community repository, integration with AI-assisted coding tools (e.g., Claude Code, Cursor) via a Model Context Protocol (MCP) server, and support for masked genome sequences. We also plan to bridge AutoBSgenome with the Bioconductor AnnotationHub framework and explore Zenodo-based archiving for genomes that exceed GitHub's per-file size limits.

## Data Availability

AutoBSgenome is freely available at https://autobsgenome.pages.dev. The community BSgenome repository is browsable at https://johnnychen1113.github.io/autoBSgenome. Source code is hosted at https://github.com/JohnnyChen1113/autoBSgenome under the GPL-3.0 license. API documentation is available at https://github.com/JohnnyChen1113/autoBSgenome/blob/main/docs/API.md.

## Funding

This work was supported by the National Science Foundation [grant number 1951332 to Z.L.].

## References

Cox E, Tsuchiya MTN, Ciufo S, et al (2025) NCBI Taxonomy: enhanced access via NCBI Datasets. Nucleic Acids Research 53:D1313–D1319

Huber W, Carey VJ, Gentleman R, et al (2015) Orchestrating high-throughput genomic analysis with Bioconductor. Nature Methods 12:115–121

Kent WJ, Sugnet CW, Furey TS, et al (2002) The Human Genome Browser at UCSC. Genome Research 12:996–1006

Lawrence M, Huber W, Pages H, et al (2013) Software for Computing and Annotating Genomic Ranges. PLoS Computational Biology 9:e1003118

Lawrence M, Gentleman R, Carey V (2009) rtracklayer: an R package for interfacing with genome browsers. Bioinformatics 25:1841–1842

Lu Z, Berry K, Bhargava T, et al (2021) TSSr: an R package for comprehensive analyses of TSS sequencing data. NAR Genomics and Bioinformatics 3:lqab108

Pages H, Aboyoun P, Gentleman R, DebRoy S. BSgenome: Software infrastructure for efficient representation of full genomes and their SNPs. R/Bioconductor package. https://bioconductor.org/packages/BSgenome

Pages H. BSgenomeForge: Forge BSgenome data packages. R/Bioconductor package. https://bioconductor.org/packages/BSgenomeForge

Sayers EW, Bolton EJ, Brister JR, et al (2023) Database resources of the National Center for Biotechnology Information in 2023. Nucleic Acids Research 51:D483–D488

Wren JD (2017) Bioinformatics programs are 31-fold over-represented among the highest impact scientific papers. Bioinformatics 33:2773–2779

Yates A, Beal K, Keenan S, et al (2015) The Ensembl REST API: Ensembl Data for Any Language. Bioinformatics 31:143–145

Wilkinson MD, Dumontier M, Aalbersberg IJ, et al (2016) The FAIR Guiding Principles for scientific data management and stewardship. Scientific Data 3:160018
