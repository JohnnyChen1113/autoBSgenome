# AutoBSgenome: a zero-setup web tool for building BSgenome R packages from any genome assembly

**Junhao Chen and Zhenguo Lin***

Department of Biology, Saint Louis University, St. Louis, MO 63103, USA

*Corresponding author: zhenguo.lin@slu.edu

---

## Abstract

BSgenome data packages are foundational components of the R/Bioconductor ecosystem, providing efficient access to full reference genome sequences for a wide range of downstream analytical tools. However, only approximately 30 model organisms have pre-built BSgenome packages available on Bioconductor, and the process of constructing custom packages for non-model organisms requires specialized software, complex file formatting, and substantial technical expertise. Here, we present AutoBSgenome, a freely available web-based tool that automates the complete BSgenome package construction workflow. Users need only enter an NCBI or Ensembl genome assembly accession; the tool automatically retrieves all required metadata, detects circular sequences, generates standards-compliant package files, and produces a downloadable, installable BSgenome package in under one minute. AutoBSgenome is implemented as a serverless application using Cloudflare Pages, Cloudflare Workers, and GitHub Actions, operating entirely within free-tier allocations to ensure long-term sustainability at zero operating cost. The tool is freely accessible at https://autobsgenome.pages.dev and the source code is available at https://github.com/JohnnyChen1113/autoBSgenome.

---

## Introduction

Reference genome sequences form the foundation of nearly all modern genomic analyses, from transcription start site profiling to motif discovery and chromatin immunoprecipitation studies. In the R/Bioconductor ecosystem, BSgenome packages serve as the standard mechanism for storing, distributing, and providing programmatic access to full genome sequences (1, 2). These packages encapsulate entire reference assemblies in a compact, memory-efficient format built on Biostrings objects, enabling seamless interoperability with a broad suite of downstream analytical tools. Packages such as TSSr (3), motifmatchr, Gviz, GenomicFeatures (4), and ChIPseeker all depend on BSgenome objects to retrieve sequence data on demand, making BSgenome packages an essential component of genome-aware workflows in R.

Despite their central role, only approximately 30 model organisms have pre-built BSgenome packages available through the Bioconductor repository. This stands in stark contrast to the millions of sequenced genomes deposited in the National Center for Biotechnology Information (NCBI) databases, spanning an ever-expanding diversity of organisms across all domains of life (5). Researchers working on non-model organisms — which now constitute the majority of active genome-scale studies — must therefore build custom BSgenome packages from scratch before they can employ the rich analytical infrastructure that depends on them.

Constructing a custom BSgenome package is, however, a nontrivial undertaking. The process requires a working installation of both Python and R, the UCSC faToTwoBit utility for converting FASTA sequences to the 2bit format (6), and the BSgenomeForge Bioconductor package (7). The user must compose a seed file in Debian Control File (DCF) format containing no fewer than 15 fields that specify the package name, title, description, organism metadata, genome provider, sequence source, and related parameters. The package name itself must conform to a strict four-part convention (BSgenome.Organism.Provider.Assembly), and the title and description must follow the wording conventions established by existing Bioconductor BSgenome packages. Once the seed file has been correctly authored, the user must invoke `forgeBSgenomeDataPkg()` to generate the package source tree and then execute `R CMD build` to produce an installable tarball. Each of these steps is prone to subtle errors that are difficult to diagnose, particularly for researchers whose primary expertise lies outside software engineering.

The BSgenomeForge package does provide a convenience function, `forgeBSgenomeDataPkgFromNCBI()`, that can automate portions of this workflow for NCBI assemblies. In practice, however, this function operates smoothly only for the roughly 50 to 60 organisms whose assemblies are registered in GenomeInfoDb, the Bioconductor package that maintains curated mappings between sequence names and chromosome conventions (8). For all other organisms — which is to say, the vast majority — the function either fails outright or requires extensive manual intervention to supply the missing metadata.

The practical consequences of this complexity are readily apparent in real-world usage. Users of the TSSr package, for example, have repeatedly requested that its developers remove the BSgenome dependency entirely, not because the BSgenome framework itself is inadequate, but because the process of constructing a custom package for their organism of interest proved prohibitively difficult. This feedback reveals a critical insight: the barrier to adoption lies not in the BSgenome infrastructure per se, but in the difficulty of building a BSgenome package for organisms that fall outside the narrow set of well-supported model species.

To address this gap, we developed AutoBSgenome, a freely available web-based tool that reduces the entire BSgenome package construction process to a single interaction requiring no local software installation, no programming knowledge, and no familiarity with the underlying build toolchain. A researcher need only paste a genome assembly accession number — from either NCBI or Ensembl — into the web interface. AutoBSgenome automatically retrieves the relevant metadata, populates all required fields, and executes the full build pipeline on cloud infrastructure, producing a downloadable, installable BSgenome package in under one minute. By eliminating every manual step in the package construction workflow while preserving full compatibility with the Bioconductor ecosystem, AutoBSgenome makes the entire BSgenome-dependent analytical toolchain accessible to any researcher working with any sequenced organism.

## Materials and Methods

### System architecture

AutoBSgenome is implemented as a serverless web application composed of four loosely coupled components: a static frontend, an API proxy layer, a containerized build pipeline, and artifact storage (Figure 1). All components operate within the free tiers of their respective hosting platforms, ensuring that the tool incurs zero ongoing cost and can be maintained indefinitely without dedicated funding.

The frontend is built with Next.js and styled using Tailwind CSS with shadcn/ui interface components. It is deployed as a static site on Cloudflare Pages, which provides global content delivery with no hosting fees. The interface presents a single input field for genome assembly accession numbers, a metadata preview panel with editable fields, and a build status monitor with a download link upon completion.

The API proxy consists of a Cloudflare Worker comprising approximately 100 lines of JavaScript. This lightweight serverless function serves two purposes: it securely encapsulates the GitHub Personal Access Token required to trigger build workflows, preventing credential exposure on the client side, and it relays build requests from the frontend to the GitHub Actions API. By isolating authentication logic in the proxy layer, the frontend remains a purely static application with no server-side secrets.

### Metadata retrieval and validation

AutoBSgenome supports genome assemblies from two major repositories. For NCBI assemblies, the tool queries the NCBI Datasets API v2 (5). The dataset_report endpoint is used to retrieve organism taxonomy, assembly name, submitting organization, and other descriptive metadata. The sequence_reports endpoint is queried separately to enumerate individual sequences and to identify circular molecules (such as mitochondrial and plastid genomes) by inspecting the `assigned_molecule_location_type` field returned for each sequence. For Ensembl assemblies, the tool queries the Ensembl REST API (9), using the `/info/assembly/{species}` endpoint to obtain assembly-level metadata and the karyotype data structure to detect circular sequences.

Retrieved metadata is used to auto-generate all fields required for the BSgenome seed file. The package name is constructed in the canonical `BSgenome.Organism.Provider.Assembly` format, where the organism binomial, data provider, and assembly identifier are extracted and formatted programmatically. The package title and description are generated following the official BSgenome convention — for example, "Full genome sequences for *Mus musculus* (Mouse) as provided by NCBI (GRCm39) and stored in Biostrings objects" — ensuring consistency with existing Bioconductor packages.

Input validation is performed at multiple stages. The four-part package name is checked against the required format before submission. When a user provides a GenBank accession (GCA_ prefix) for an assembly that lacks organelle annotation data, AutoBSgenome detects this condition and suggests the corresponding RefSeq accession (GCF_ prefix), which typically provides more complete metadata including organelle sequence classification. All auto-populated fields remain editable in the interface, allowing users to override defaults when necessary.

### Build pipeline

The build pipeline executes on GitHub Actions using a pre-built Docker image based on rocker/r-ver:4.4.0. This image is augmented with the BSgenome and BSgenomeForge Bioconductor packages, the UCSC faToTwoBit binary, and the NCBI Datasets command-line tool, all pre-installed to minimize build time. The pipeline proceeds through five sequential stages: (i) the reference genome FASTA file is downloaded from the appropriate source repository using either the NCBI Datasets CLI or direct Ensembl FTP retrieval; (ii) the FASTA file is converted to UCSC 2bit format using faToTwoBit; (iii) a seed file is generated from the validated metadata; (iv) the `forgeBSgenomeDataPkg()` function is invoked within R to produce the package source directory; and (v) `R CMD build` is executed to create the final compressed tarball.

### Artifact storage and lifecycle

Completed package tarballs are uploaded as GitHub Release assets, which are publicly accessible via direct download URLs returned to the user through the frontend. An automated cleanup workflow removes release artifacts older than 14 days to manage storage consumption within the free tier. Users are advised to download their packages promptly or to re-trigger a build if needed after the retention period has elapsed.

### Availability and cost

The complete AutoBSgenome source code is available under the GPL-3.0 license at https://github.com/JohnnyChen1113/autoBSgenome. The hosted instance is freely accessible at https://autobsgenome.pages.dev. A programmatic API is also provided (documented at https://github.com/JohnnyChen1113/autoBSgenome/blob/main/docs/API.md), enabling integration with automated workflows. All infrastructure components — Cloudflare Pages, Cloudflare Workers, GitHub Actions, and GitHub Releases — operate within their respective free-tier allocations, ensuring that the tool remains available at zero cost to both users and maintainers.

## Results

### Performance evaluation

To evaluate the performance of AutoBSgenome, we measured build times using the genome of *Aspergillus luchuensis* (GCF_016861625.1), a non-model filamentous fungus with a genome size of approximately 33 MB. When the pre-built Docker image was available from GitHub Container Registry, the complete workflow — from user submission to downloadable BSgenome package — completed in approximately 46 seconds. On a first run without a cached Docker image, the total time increased to approximately 9 minutes, a duration dominated by the one-time installation of R and Bioconductor dependencies. Because the Docker image is built once and cached persistently on GitHub Container Registry, subsequent builds for any user consistently achieved the faster execution time. For larger genomes, such as the human reference assembly (~3 GB), build time is estimated at approximately 5 minutes, with FASTA download constituting the primary bottleneck rather than package compilation.

### Comparison with existing approaches

We compared AutoBSgenome with the two principal existing methods for constructing BSgenome data packages: the manual procedure documented in the BSgenome vignette and the BSgenomeForge command-line interface. The results of this comparison are summarized in Table 1.

**Table 1.** Feature comparison of BSgenome package construction methods.

| Feature | Manual process | BSgenomeForge CLI | AutoBSgenome Web |
|---|---|---|---|
| Local R installation required | Yes | Yes | No |
| faToTwoBit utility required | Yes | No | No |
| Metadata auto-fill | None | Partial (registered only) | Full (NCBI + Ensembl) |
| Non-registered organism support | Manual seed file | Requires extra arguments | Fully supported |
| Old assembly version support | Manual seed file | Ambiguous resolution | Direct accession support |
| Circular sequence detection | Manual | Auto (registered only) | Auto (all organisms) |
| Steps required by user | ~10 | ~3 | 3 |
| Estimated time to first package | 30–60 min | 10–15 min | <1 min |

### Data source support

AutoBSgenome accepts genome assemblies from two major repositories. For NCBI, both RefSeq (GCF_) and GenBank (GCA_) accession numbers are supported at any version, with metadata retrieved programmatically through the NCBI Datasets API v2. For Ensembl, users may provide either a species URL or a species name, from which the tool automatically resolves the current assembly and retrieves sequence data. When a user submits a GenBank accession for an assembly that lacks organelle annotation, AutoBSgenome detects this condition and suggests the corresponding RefSeq accession where circular sequence metadata is typically available.

### Case study: BSgenome construction for a non-model organism

To demonstrate a representative use case, we constructed a BSgenome package for *Aspergillus luchuensis* (GCF_016861625.1), an industrially relevant koji mold not available as a pre-built BSgenome package on Bioconductor. Researchers requiring BSgenome-dependent analyses for this organism — for example, transcription start site profiling with TSSr (3) — would have needed to construct the package manually. Using AutoBSgenome, we entered the RefSeq accession, confirmed the auto-populated metadata fields, and initiated the build. The resulting package, BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308 (9.3 MB), was produced in 46 seconds and was immediately installable in R via `install.packages()`. No local software installation, command-line interaction, or knowledge of BSgenome seed file format was required at any point in this process.

## Discussion

AutoBSgenome addresses a persistent accessibility gap in the Bioconductor ecosystem. Although BSgenome data packages serve as a foundational dependency for numerous genomics tools, constructing these packages for organisms not already represented on Bioconductor has remained a nontrivial task. The difficulty is not primarily computational but procedural: users must navigate seed file syntax, locate and convert FASTA files, identify circular sequences, and maintain a compatible R/Bioconductor environment. For biologists and clinician-scientists who require BSgenome packages as an intermediate step rather than an end in themselves, this overhead can be prohibitive. Indeed, our motivation for developing AutoBSgenome arose from observing that users of the TSSr package (3) were frequently unable to proceed with analyses because BSgenome construction presented an insurmountable barrier. By reducing the entire workflow to a web-based interaction requiring no local software, AutoBSgenome transforms BSgenome package construction from a specialist task into a routine operation.

The zero-cost serverless architecture underlying AutoBSgenome merits consideration as a model for sustainable open-source bioinformatics tool deployment. A well-documented challenge in the bioinformatics community is the disappearance of web tools within years of publication, often due to the unsustainable costs of server maintenance (10). By leveraging GitHub Actions for computation, GitHub Container Registry for image caching, and Cloudflare's free-tier hosting for the frontend and API, AutoBSgenome eliminates infrastructure costs entirely. This approach ensures that the tool can remain operational indefinitely without dedicated funding — a critical consideration for tools that serve a global community of researchers over extended time periods.

A notable design decision was the adoption of the NCBI Datasets API v2 as the primary metadata retrieval interface. Compared with the traditional NCBI E-utilities, the Datasets API provides structured JSON responses that directly expose assembly metadata, sequence reports, and organism taxonomy in a format amenable to programmatic extraction (5). This enabled AutoBSgenome to auto-populate all required BSgenome metadata fields — including organism name, assembly name, sequence names, and circular sequence annotations — without requiring users to consult external databases or documentation. The practical consequence is that AutoBSgenome supports any organism with an NCBI assembly record, regardless of whether that organism has been registered in Bioconductor's curated GenomeInfoDb database.

By making BSgenome package construction trivially accessible, AutoBSgenome also has implications for the broader design of Bioconductor tools. Several package developers have considered removing BSgenome dependencies in favor of direct FASTA file input, citing the difficulty users experience in obtaining BSgenome packages for non-model organisms. AutoBSgenome diminishes the rationale for such architectural changes, allowing tool developers to retain the advantages of BSgenome's standardized genome representation — including lazy loading, consistent naming, and integration with other Bioconductor infrastructure — without imposing undue burden on end users.

Several limitations of the current implementation should be noted. First, very large genomes exceeding approximately 10 GB may approach the six-hour timeout imposed by GitHub Actions, although genomes of this size are uncommon outside polyploid plant species. Second, Ensembl FASTA filename patterns exhibit occasional variation across species, which may cause retrieval failures for certain organisms; we address such cases as they are reported through the integrated issue reporting mechanism. Third, AutoBSgenome does not currently support upload of user-provided FASTA files, limiting its use to genomes available through NCBI or Ensembl; support for custom FASTA input is planned for a future release. Finally, the 14-day artifact retention policy means that users must download their packages promptly, as builds are not permanently hosted.

Future development priorities include integration with R-universe (https://r-universe.dev) for persistent, installable package hosting that would eliminate the retention limitation entirely. We also envision a community-maintained BSgenome registry in which user-built packages are catalogued and shared, reducing redundant builds across the research community. Longer-term goals include integration with the Bioconductor AnnotationHub framework and support for masked genome sequences, which would extend AutoBSgenome's utility to applications requiring repeat-masked reference data.

## Data Availability

AutoBSgenome is freely available at https://autobsgenome.pages.dev. Source code is hosted at https://github.com/JohnnyChen1113/autoBSgenome under the GPL-3.0 license. API documentation is available at https://github.com/JohnnyChen1113/autoBSgenome/blob/main/docs/API.md.

## Funding

This work was supported by the National Science Foundation [grant number 1951332 to Z.L.].

## References

1. Pages H, Aboyoun P, Gentleman R, DebRoy S. BSgenome: Software infrastructure for efficient representation of full genomes and their SNPs. R package, Bioconductor. https://bioconductor.org/packages/BSgenome
2. Huber W, Carey VJ, Gentleman R, et al. Orchestrating high-throughput genomic analysis with Bioconductor. *Nature Methods* 2015;12:115-121.
3. Lu Z, Berry K, Bhargava T, et al. TSSr: an R package for comprehensive analyses of TSS sequencing data. *NAR Genomics and Bioinformatics* 2021;3:lqab108.
4. Lawrence M, Huber W, Pages H, et al. Software for Computing and Annotating Genomic Ranges. *PLoS Computational Biology* 2013;9:e1003118.
5. Cox E, Tsuchiya MTN, Ciufo S, et al. NCBI Taxonomy: enhanced access via NCBI Datasets. *Nucleic Acids Research* 2025;53:D1313-D1319.
6. Kent WJ, Sugnet CW, Furey TS, et al. The Human Genome Browser at UCSC. *Genome Research* 2002;12:996-1006.
7. Pages H. BSgenomeForge: Forge BSgenome data packages. R package, Bioconductor. https://bioconductor.org/packages/BSgenomeForge
8. Lawrence M, Gentleman R, Carey V. rtracklayer: an R package for interfacing with genome browsers. *Bioinformatics* 2009;25:1841-1842.
9. Yates A, Beal K, Keenan S, et al. The Ensembl REST API: Ensembl Data for Any Language. *Bioinformatics* 2015;31:143-145.
10. Wilkinson MD, Dumontier M, Aalbersberg IJ, et al. The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data* 2016;3:160018.
