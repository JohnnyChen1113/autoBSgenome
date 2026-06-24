# autoBSgenome: accession-driven construction and repository-scale distribution of Bioconductor BSgenome packages

Junhao Chen and Zhenguo Lin*

Department of Biology, Saint Louis University, St. Louis, MO 63103, USA

*Corresponding author: zhenguo.lin@slu.edu

---

## Abstract

BSgenome data packages provide standardized, versioned access to reference genome sequences within R/Bioconductor. They are the sequence substrate for coordinate-aware workflows in ChIP-seq, ATAC-seq, bisulfite sequencing, variant annotation, mutational signature analysis, CRISPR guide design and related domains. Yet the availability of pre-built BSgenome packages remains narrow: Bioconductor hosts 113 BSgenome data packages covering 33 organisms, while thousands of reference assemblies are available through NCBI and Ensembl. For any organism outside this model-species set, researchers must manually download FASTA files, determine circular sequences, write a BSgenome seed file, convert sequence data to UCSC 2bit, forge the package and build a distributable tarball. We present autoBSgenome, a web service and package repository that turns this construction process into an accession-driven workflow. Users provide an NCBI or Ensembl assembly identifier, a FASTA download URL, or their own FASTA file; autoBSgenome retrieves metadata, detects circular sequences when public assembly reports are available, validates nucleotide FASTA inputs, generates the seed file, builds the package and returns an installable tarball. Browser FASTA uploads use multipart transfer to private staging storage, and resulting on-demand packages are delivered as temporary GitHub Release assets that can be deleted immediately or removed by scheduled cleanup after two days. User-supplied packages enter the permanent public index only through explicit public-release opt-in with user-asserted provenance and license metadata. We benchmarked the pipeline across 33 genomes spanning fungi, plants and vertebrates, with median build times below one minute for small genomes and 2-5 min for vertebrate-scale assemblies. We further built a public CRAN-like repository containing 3,940 autoBSgenome packages covering 3,100 organisms, alongside a catalog of the 113 Bioconductor-hosted BSgenome packages. Large-genome stress tests show that assembly fragmentation, rather than genome size alone, is the practical build limit: a 34.56 GB chromosome-level lungfish genome built successfully, whereas a smaller but highly fragmented axolotl assembly exceeded runner memory. By reducing BSgenome construction to accession entry, FASTA URL, or FASTA upload, autoBSgenome removes a practical barrier to Bioconductor analyses in non-model organisms.

**Availability:** Web service: https://autobsgenome.org. Package repository: https://johnnychen1113.github.io/autoBSgenome. Source code: https://github.com/JohnnyChen1113/autoBSgenome.

---

## Introduction

Reference genome sequences are a routine input to modern genomic analysis, but in Bioconductor they are more than files on disk. A BSgenome package wraps a reference assembly in UCSC 2bit format and exposes it through a uniform R API, so that downstream tools can retrieve sequence by genomic coordinates while preserving assembly metadata. The same `getSeq()` call can extract bases for ChIP-seq peaks, ATAC-seq accessible regions, methylated loci, CRISPR protospacers or variant contexts, provided that the organism has a matching BSgenome package.

A FASTA file alone does not provide the same reproducibility unit. Indexed FASTA can support random-access retrieval, but it does not carry Bioconductor's sequence metadata through the type system. In a BSgenome package, sequence names, seqlengths, circularity flags and genome identifiers are first-class objects that propagate into `GRanges`, `VCF`, `SummarizedExperiment` and related containers. Circularity is not cosmetic: mitochondrial, plastid and plasmid coordinate logic depends on whether a molecule is declared circular. BSgenome packages are also versioned software artifacts. A manuscript that reports `BSgenome.Hsapiens.UCSC.hg38` at a specific package version names an installable dependency, whereas a manuscript that cites a FASTA URL depends on external file state and local preprocessing.

This distinction matters because BSgenome is embedded throughout the Bioconductor ecosystem. In a project census of Bioconductor package metadata collected in 2026, 118 software packages include BSgenome in `Depends`, `Imports` or `LinkingTo`, and 206 packages list BSgenome anywhere in their DESCRIPTION dependency fields. These packages span CRISPR guide design, motif discovery, ChIP-seq and ATAC-seq analysis, methylation calling, variant annotation, mutational signatures, genome visualization and transcription start site profiling. Public Bioconductor download statistics further show that BSgenome is used at production scale: the infrastructure package received approximately 490,000 downloads in 2025, and the most-downloaded human, mouse and fly BSgenome packages together accounted for hundreds of thousands of annual downloads.

The barrier is that BSgenome is per-organism. Universal infrastructure packages such as GenomicRanges or Biostrings are installed once and reused across all assemblies. BSgenome does not work that way. A human workflow requires one species-specific data package; the same workflow in mouse requires another; the same workflow in a newly sequenced plant, fish, fungus or microbe requires a package that may not exist. Bioconductor currently hosts 113 BSgenome data packages, covering 33 organisms and a small set of historical assembly versions. The remaining long tail of public reference assemblies is outside the ready-to-install BSgenome universe.

Manual package construction is possible but operationally brittle. A user must identify the correct assembly FASTA, normalize sequence headers, determine circular molecules, write a Debian Control File style seed file with BSgenome-specific fields, convert the genome to 2bit, run `forgeBSgenomeDataPkg()`, build the source package and distribute the resulting tarball. Each stage has failure modes: NCBI and Ensembl use different metadata conventions; organelle sequences are not consistently named; circularity may be present in assembly reports but absent from FASTA headers; large genomes encounter 2bit, tar and artifact-size limits; and seed-file errors often surface as low-level R build failures. For researchers whose primary work is experimental biology or organismal genomics, this forgework is a gate to downstream analysis.

autoBSgenome was built around a simple premise: an assembly accession should be enough. For public assemblies, the service converts NCBI and Ensembl identifiers into installable BSgenome packages without local software, command-line interaction or seed-file authoring. For assemblies hosted outside those sources, users can provide a FASTA URL; for assemblies not yet deposited in public databases, they can upload a FASTA file and receive a temporary BSgenome package for local installation. In parallel, autoBSgenome systematically pre-builds and indexes packages from public sources, so that many users can install directly from a CRAN-like repository rather than rebuild. The goal is concrete: no BSgenome should be hard to build.

## Materials and Methods

### System overview

autoBSgenome consists of a web frontend, an API layer, a containerized build workflow and a package repository. The frontend collects either an NCBI accession, an Ensembl species/assembly identifier, a FASTA download URL or a user FASTA upload. The API validates the request and triggers a GitHub Actions workflow through a repository dispatch payload. The build workflow runs in a Docker image containing R, Bioconductor, BSgenome, BSgenomeForge, faToTwoBit, the NCBI Datasets CLI and project scripts. Successful builds produce standard source tarballs installable through `install.packages(..., repos = NULL, type = "source")`.

The public repository is maintained separately from temporary on-demand builds. Packages built from public NCBI or Ensembl inputs can be added to the permanent index with provider-derived provenance. User-supplied FASTA URL and upload builds are returned first as temporary GitHub Release downloads. The web interface exposes a delete action for the current build release, and scheduled cleanup removes temporary build artifacts after two days. A user-supplied package can be added to the permanent public repository only when the user explicitly opts into public redistribution, confirms rights to redistribute the sequence-derived package and provides provenance and license metadata. These community-submitted records are represented as user-asserted rather than provider-verified provenance.

### Input modes and metadata retrieval

For NCBI builds, autoBSgenome uses the NCBI Datasets API and command-line client to resolve assembly accessions, retrieve assembly metadata and download genome FASTA files. The metadata layer captures scientific name, common name when available, assembly name, provider, release date, accession and source URL. For Ensembl builds, autoBSgenome resolves species pages and release-specific FASTA locations through Ensembl metadata endpoints and local resolver logic for group-specific directory conventions.

User-supplied FASTA builds use the same package-generation path after sequence download. For URL-based inputs, GitHub Actions downloads the FASTA directly from the provided HTTP(S) URL. For browser uploads, the frontend performs a preflight check on the first decoded FASTA segment, including gzip-compressed input when supported by the browser, and rejects FASTQ-like content, protein FASTA extensions and alphabets inconsistent with nucleotide or IUPAC ambiguity codes. Accepted files are uploaded as multipart objects to private Cloudflare R2 staging storage, with 64 MB parts and a 4 GiB application limit. The API passes a signed download URL and delete URL to the build workflow, and R2 lifecycle rules expire abandoned upload objects after two days. Both uncompressed FASTA and gzip-compressed FASTA are accepted with `.fa`, `.fasta`, `.fna`, `.fas` or corresponding `.gz` filename extensions.

### Circular sequence detection

For NCBI assemblies, circular sequence detection uses assembly sequence reports rather than FASTA names alone. The workflow inspects sequence-level metadata for molecule type and location flags, then maps mitochondrial, chloroplast, plastid, plasmid, apicoplast and kinetoplast records into the BSgenome `circ_seqs` field. For Ensembl inputs, circularity is inferred from karyotype and organelle naming conventions when available. Users can review and edit the circular sequence field before build submission.

This step is biologically important because BSgenome circularity metadata affects downstream coordinate handling. The workflow therefore treats circular sequence detection as part of package metadata, not as a cosmetic annotation.

### Package generation

The build pipeline has five core stages: FASTA acquisition, 2bit conversion, seed-file generation, BSgenome forging and R source package construction. FASTA acquisition is source-specific. NCBI assemblies are downloaded with `datasets download genome accession`; Ensembl assemblies are resolved to group-specific FASTA URLs; user-provided FASTA URLs are downloaded directly; uploaded FASTA files are downloaded from the signed object URL and decompressed when necessary. Before 2bit conversion, all user-supplied FASTA inputs pass a streaming nucleotide FASTA validator that rejects malformed FASTA, FASTQ records and protein alphabets.

The genome FASTA is converted to UCSC 2bit format with faToTwoBit. For large inputs, the workflow uses the `-long` option to avoid the default 4 GB 2bit index limit. The seed file is generated programmatically with package name, title, description, version, organism, common name, genome, provider, release date, source URL, circular sequences and 2bit file location. The seed file is then passed to `forgeBSgenomeDataPkg()`. Finally, `R CMD build` assembles the distributable tarball. For large packages, the workflow sets `R_BUILD_TAR=tar` so that R uses the external GNU tar implementation rather than the internal tar implementation that fails near 8 GB package sizes.

### Artifact storage and repository indexing

Build artifacts below the GitHub Releases single-asset safety threshold are stored as GitHub Release assets. Larger public-source packages are routed to Zenodo records and linked from the package index. On-demand user-supplied builds are also delivered through temporary GitHub Release assets, but they are not treated as permanent repository records unless the user completes the public-release opt-in flow. Temporary build releases can be deleted from the web interface and are also removed by scheduled cleanup after two days. The repository index is maintained in CRAN-like form through `src/contrib/PACKAGES`, with richer metadata stored in `packages.json`. The cleanup state reported here treats `packages.json` as the canonical source of truth for the public repository. As of June 24, 2026, this file contains 3,940 autoBSgenome packages covering 3,100 organisms.

Each permanent public package record includes package name, version, organism, assembly, provider, accession when available, file name, file size, source URL and selected build provenance. Provenance fields include build time, workflow run identifiers, builder image, package checksum and DESCRIPTION checksum when available. Community-submitted records additionally store source type, submitted source URL when applicable, license metadata, public opt-in state and `provenance_status = "user_asserted"` to distinguish user-declared provenance from provider-derived NCBI or Ensembl metadata.

### Benchmarks and large-genome stress tests

We evaluated on-demand build behavior using a 33-genome benchmark spanning fungi, plants, algae and vertebrates. The benchmark records input genome size, package size, build success and wall-clock runtime. We also performed large-genome stress tests to determine practical limits of the current hosted build environment. These stress tests included chromosome-level and fragmented assemblies ranging from 14.57 GB to 34.56 GB.

For repository-scale status, we used the cleaned `packages.json` index rather than historical queue counters. The queue file records build-dispatch history and may contain legacy naming drift, whereas `packages.json` records packages actually present in the installable public repository.

## Results

### Accession-driven package construction

autoBSgenome reduces BSgenome construction to a short user workflow. A user selects NCBI or Ensembl, enters an accession or species page, reviews auto-filled metadata and starts the build. The resulting package can be installed directly in R from the returned tarball URL. The workflow removes seed-file authoring, local R setup, command-line FASTA conversion and manual circular-sequence lookup from the user's path.

The same backend also supports FASTA URLs and FASTA upload for assemblies not yet represented in NCBI or Ensembl. In these modes, the user still provides package metadata but supplies sequence data directly or by download URL. User-supplied FASTA builds are useful for draft assemblies, teaching examples and controlled deployments with appropriate artifact-storage policies. By default, they produce temporary packages for local installation. When users explicitly choose public release, confirm redistribution rights and provide license and source metadata, the same build can be promoted to the permanent repository as a community-submitted package with user-asserted provenance.

### Benchmark performance across 33 genomes

The 33-genome benchmark completed successfully across all selected fungi, plants/algae and vertebrates (Table 1). Small fungal genomes built in under one minute, plant and algal genomes in roughly the same range for the tested sizes, and vertebrate-scale genomes in approximately 2-5 min. The median build time for genomes below 100 MB was 44 s, and the overall benchmark median was 52 s. All generated packages installed in a clean R session and exposed expected BSgenome sequence names.

**Table 1. Benchmark summary for on-demand BSgenome package construction.**

| Group | Species tested | Genome size range | Median build time | Build success | Package size range |
|---|---:|---:|---:|---:|---:|
| Fungi / Microsporidia | 12 | 2.2-33 MB | 44 s | 12/12 | 0.6-9.3 MB |
| Plants / Algae | 11 | 12.9-133.1 MB | 52 s | 11/11 | 3.5-34 MB |
| Vertebrates | 10 | 366-674 MB | 148 s | 10/10 | 122-173 MB |
| Total | 33 | 2.2-674 MB | 52 s | 33/33 | 0.6-173 MB |

The benchmark confirms that routine microbial, fungal, plant and vertebrate assemblies can be converted quickly enough for interactive web use. Build time scales with input and output size, but for common eukaryotic assemblies the workflow remains within a single browser session.

### Public BSgenome repository coverage

The permanent autoBSgenome repository currently contains 3,940 auto-built packages covering 3,100 organisms, plus records for 113 Bioconductor-hosted BSgenome packages. Among auto-built packages, 2,073 are Ensembl-derived and 1,867 are NCBI-derived. The repository spans major organism groups, including fungi (1,194 packages), invertebrates (462), other vertebrates (398), mammalian vertebrates (380), plants (339), archaea (379), bacteria (198) and additional organisms outside these bins (590). At the domain level, the index includes 2,993 eukaryotic packages, 379 archaeal packages and 198 bacterial packages, with 370 records not assigned to a domain in the current metadata.

This represents a substantial expansion beyond the 113 BSgenome packages available through Bioconductor. Bioconductor packages remain the preferred upstream source when they exist, but autoBSgenome fills the long tail where no official package has been provided. Users can search the web interface by package name, organism, accession, provider and taxonomic grouping, then install packages through:

```r
install.packages("BSgenome.Tflavidus.NCBI.ASM371156v2",
  repos = "https://johnnychen1113.github.io/autoBSgenome")
```

The repository is designed as an installation surface, not just a build log. The canonical `packages.json` file backs the web interface and paper counts, while `src/contrib/PACKAGES` supports R's standard package installation mechanism.

### Resource index finalization

For manuscript reporting, autoBSgenome separates build-dispatch history from installable package state. Historical queue records are useful for operations, but they include retries, archived dispatches and legacy naming drift. The public resource count is therefore derived from `packages.json`, the same machine-readable index that backs the web interface and package metadata pages. At resource freeze, `packages.json` and the R-facing `src/contrib/PACKAGES` index were validated together, and the three final missing release assets were backfilled into both indexes. This produced the finalized count of 3,940 unique autoBSgenome packages across 3,100 organisms.

### Assembly contiguity is the practical large-genome limit

Large-genome stress tests revealed that build feasibility is not determined by raw genome size alone (Table 2). The clearest comparison is between axolotl and Australian lungfish. The axolotl assembly was 28.21 GB with 27,157 contigs and failed at the R forge stage due to memory exhaustion. The lungfish assembly was larger at 34.56 GB but chromosome-level, with 46-50 major sequences depending on reporting, and built successfully in 35 min 20 s with a forge-stage peak RSS of approximately 708 MB.

**Table 2. Large-genome stress tests on the autoBSgenome build pipeline.**

| Organism | Assembly | Raw size | Sequence records | Outcome | Wall-clock | Forge peak RSS |
|---|---|---:|---:|---|---:|---:|
| *Triticum aestivum* | IWGSC RefSeq v2.1 | 14.57 GB | ~21 scaffolds | Built | 12:05 | Not recorded |
| *Pinus taeda* | Ptaeda2.0 | 22.10 GB | Several thousand scaffolds | Built | 34:18 | Not recorded |
| *Ambystoma mexicanum* | AmbMex60DD | 28.21 GB | 27,157 contigs | OOM at R forge | - | >16 GB |
| *Neoceratodus forsteri* | neoFor_v3.1 | 34.56 GB | 46 chromosome-level sequences | Built | 35:20 | 708 MB |

This same-stack comparison isolates assembly fragmentation as the binding axis. `forgeBSgenomeDataPkg()` creates per-record R objects and metadata, so a highly fragmented draft assembly can exhaust memory even when a larger chromosome-level assembly succeeds. The observation is practically useful for users: high-quality chromosome-level assemblies are more likely to build successfully than smaller but fragmented assemblies. For draft assemblies with tens of thousands of contigs, future versions of autoBSgenome should offer optional minimum-contig-length filtering or self-hosted runner profiles with more memory.

## Discussion

autoBSgenome addresses a specific accessibility problem in computational genomics: many Bioconductor workflows are available in principle for any organism, but in practice require an organism-specific BSgenome package before analysis can begin. By automating package construction and pre-building a broad repository, autoBSgenome makes this prerequisite available to researchers working outside the canonical model species.

The contribution is not a new sequence representation. autoBSgenome relies on existing and trusted infrastructure: NCBI Datasets, Ensembl, UCSC 2bit, BSgenomeForge and R package installation conventions. Its value is that it composes these pieces into an end-to-end workflow with the right defaults, metadata handling and artifact distribution. This is important because the manual path is not one hard problem; it is a series of small, domain-specific steps that collectively block many users.

The public repository expands the practical BSgenome surface from 113 official Bioconductor packages to 3,940 additional auto-built packages. This changes how users can approach non-model organism analysis. A lab studying a fungal pathogen, plant crop relative, invertebrate model or microbial eukaryote can now search for an installable BSgenome package before considering manual construction. If the package is absent but the assembly is public, an accession-driven build can produce it. If the FASTA is hosted elsewhere, a URL-based build can use it directly. If the user has a local nucleotide FASTA file, multipart upload provides the same local-installation path, with optional public promotion when the user is willing and authorized to release the resulting package.

Several limitations remain. First, user-uploaded FASTA inputs are staged privately and cleaned quickly, but generated packages are distributed through GitHub Release assets: temporary by default, permanent only after explicit public-release opt-in. The delete button and two-day cleanup reduce persistence, but they do not make a generated package private; users should not submit private or sensitive sequence data to the hosted public instance unless public artifact exposure is acceptable. Second, very large and highly fragmented assemblies can exceed memory or artifact limits. The stress tests suggest that chromosome-level assemblies can build well beyond 30 GB, but fragmented assemblies with tens of thousands of contigs may fail earlier. Third, the repository does not currently provide masked BSgenome variants. This is intentional for the present release, because Bioconductor's masking model can be handled as an overlay rather than a requirement for the initial unmasked genome package. Fourth, some Ensembl assemblies use non-standard FASTA naming patterns and require resolver updates as coverage expands.

The same per-organism packaging barrier exists in other Bioconductor data-package families, including TxDb, EnsDb, organism annotation databases, SNPlocs and MafDb. autoBSgenome does not claim to solve those families, but it demonstrates an accession-driven build pattern for the largest per-organism sequence-data family. Extending similar automation to transcript annotation and organism annotation packages is a natural next step.

## Figures and tables to prepare

**Figure 1. autoBSgenome workflow.** Accession, FASTA URL or local FASTA input, metadata retrieval, circular-sequence detection, FASTA acquisition and validation, 2bit conversion, seed-file generation, package forging, R CMD build, temporary package delivery, user-triggered deletion and optional public repository promotion.

**Figure 2. BSgenome accessibility gap and repository expansion.** Bioconductor-hosted BSgenome packages versus autoBSgenome packages, grouped by provider and taxonomic division.

**Figure 3. Build-time benchmark.** Scatter plot of build time versus genome size for the 33-genome benchmark, with group labels and size-class medians.

**Figure 4. Contiguity ceiling.** Large-genome stress tests showing raw genome size, sequence count, success/failure and forge-stage memory use.

**Figure 5. Repository browse interface.** Screenshot of the package search and package detail view, showing provider, accession, organism, assembly, provenance status and installation command.

## Data availability

The autoBSgenome web service is available at https://autobsgenome.org. The public package repository is available at https://johnnychen1113.github.io/autoBSgenome, with machine-readable metadata in `packages.json` and R installation metadata in `src/contrib/PACKAGES`. Source code, workflows, Docker build files and documentation are available at https://github.com/JohnnyChen1113/autoBSgenome. The v4 resource counts in this manuscript are based on the cleaned `packages.json` index as of June 24, 2026.

## Funding

This work was supported by the National Science Foundation [grant number 1951332 to Z.L.].

## References

Arora, S., Morgan, M., Carlson, M., & Pages, H. (2025). *GenomeInfoDb: Utilities for manipulating chromosome names* (R package version 1.46.0). Bioconductor. https://doi.org/10.18129/B9.bioc.GenomeInfoDb

Cox, E., Tsuchiya, M. T. N., Ciufo, S., Torcivia, J., Falk, R., Anderson, W. R., Holmes, J. B., Hem, V., Breen, L., Davis, E., Ketter, A., Zhang, P., Soussov, V., Schoch, C. L., & O'Leary, N. A. (2025). NCBI Taxonomy: Enhanced access via NCBI Datasets. *Nucleic Acids Research*, *53*(D1), D1711-D1715. https://doi.org/10.1093/nar/gkae967

Dyer, S. C., Austine-Orimoloye, O., Azov, A. G., et al. (2025). Ensembl 2025. *Nucleic Acids Research*, *53*(D1), D948-D957. https://doi.org/10.1093/nar/gkae1071

Gentleman, R. C., Carey, V. J., Bates, D. M., et al. (2004). Bioconductor: Open software development for computational biology and bioinformatics. *Genome Biology*, *5*(10), R80. https://doi.org/10.1186/gb-2004-5-10-r80

Huber, W., Carey, V. J., Gentleman, R., et al. (2015). Orchestrating high-throughput genomic analysis with Bioconductor. *Nature Methods*, *12*(2), 115-121. https://doi.org/10.1038/nmeth.3252

Kent, W. J., Sugnet, C. W., Furey, T. S., Roskin, K. M., Pringle, T. H., Zahler, A. M., & Haussler, D. (2002). The human genome browser at UCSC. *Genome Research*, *12*(6), 996-1006. https://doi.org/10.1101/gr.229102

Lawrence, M., Huber, W., Pages, H., et al. (2013). Software for computing and annotating genomic ranges. *PLoS Computational Biology*, *9*(8), e1003118. https://doi.org/10.1371/journal.pcbi.1003118

Lu, Z., Berry, K., Bhargava, T., Hu, Z., Zhan, Y., Ahn, T.-H., & Lin, Z. (2021). TSSr: An R package for comprehensive analyses of TSS sequencing data. *NAR Genomics and Bioinformatics*, *3*(4), lqab108. https://doi.org/10.1093/nargab/lqab108

Pages, H. (2025). *BSgenome: Software infrastructure for efficient representation of full genomes and their SNPs* (R package version 1.78.0). Bioconductor. https://doi.org/10.18129/B9.bioc.BSgenome

Pages, H., & Kakopo, A. K. (2025). *BSgenomeForge: Forge BSgenome data packages* (R package version 1.10.2). Bioconductor. https://doi.org/10.18129/B9.bioc.BSgenomeForge

Sayers, E. W., Bolton, E. E., Brister, J. R., et al. (2023). Database resources of the National Center for Biotechnology Information in 2023. *Nucleic Acids Research*, *51*(D1), D29-D38. https://doi.org/10.1093/nar/gkac1032

Yates, A., Beal, K., Keenan, S., et al. (2015). The Ensembl REST API: Ensembl data for any language. *Bioinformatics*, *31*(1), 143-145. https://doi.org/10.1093/bioinformatics/btu613
