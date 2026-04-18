# autoBSgenome v3 (Plan C) — Outline

**Thesis type:** Problem → Architectural Solution → Working Exemplar
**Target:** NAR Genomics & Bioinformatics (NARGAB)
**Split:** architecture/sustainability 60% · BSgenome resource 40%

---

## Working title candidates

1. **Sustainable by design: zero-marginal-cost architecture for long-lived bioinformatics resources, demonstrated with autoBSgenome**
2. **Beyond the funding cycle: compositional free-tier infrastructure for perpetual bioinformatics services**
3. **Building bioinformatics tools to outlive their grants: the autoBSgenome architecture**

(1) is the most explicit; (3) is the most pragmatic. (2) has the best bibliometric ring but may sound self-aggrandizing. We can decide with advisor.

---

## Abstract kernel (~180 words)

> The median lifespan of a published bioinformatics tool or database is under a decade, and the dominant cause of failure is not scientific obsolescence but operational: grants end, personnel leave, institutional hosting changes. This fragility is typically addressed after the fact rather than designed against. Here we propose a **compositional free-tier architecture** — systematically distributing a web service across multiple providers' perpetual free tiers (Cloudflare Pages and Workers for frontend and API, GitHub Actions for compute, GitHub Releases for artifact storage) — as a deliberate design pattern that decouples service longevity from funding and personnel. The architecture is failure-tolerant by construction: each component has a documented migration path if its provider changes terms. We demonstrate the pattern with autoBSgenome, a web service that converts any NCBI or Ensembl assembly accession into an installable Bioconductor-compatible BSgenome R package. Using this architecture, autoBSgenome systematically closes a long-standing accessibility gap, producing comprehensive BSgenome packages for 3,553 eukaryotic reference genomes at zero marginal cost. We provide the resource, the architectural pattern, and a transferability framework for applying it to other bioinformatics services.

**Key abstract moves:**
- Sentence 1 names the field-wide pain (tool longevity).
- Sentence 2–3 names the novel contribution (architecture as a pattern, not a tool).
- Sentence 4 frames failure-tolerance as design property.
- Sentence 5–7 introduce autoBSgenome as the **demonstration**, not the subject.
- Closing sentence promises the transferability framework.

---

## Introduction (~1,200 words)

**1. The tool longevity crisis (300 words)**
- Wren (2016): bioinformatics programs are 31× over-represented in high-impact papers. Demand is massive.
- Counterpoint evidence: Mangul et al. 2019 (omics tool reproducibility), Kim et al. on database link rot, Schultheiss et al. studies on tool availability — median tool lifespan ≈ 5 years, majority of paper-published links dead within 10.
- Cause analysis: Funding end → server shutdown; personnel change → unmaintained; institutional reorganization → URL move.
- **Framing claim:** Sustainability is not a second-order concern but a first-order design requirement.

**2. Existing approaches and why they fall short (300 words)**
- Traditional: PI-funded servers (dies with grant).
- Institutional: core facility hosting (dies with institutional change).
- Commercial cloud: AWS/Azure deployments (dies with budget).
- Docker images on DockerHub (dies with rate limit changes or account closure).
- **Key gap:** none of these are architecturally immortal; all are economically bounded.

**3. The compositional free-tier pattern (400 words)**
- Observation: no single free tier supports a complete bioinformatics service, but **combinations of free tiers do**.
- Design principle: decompose a service into (a) static frontend, (b) stateless API, (c) ephemeral compute, (d) immutable artifact storage — each served by a different provider's perpetual free tier.
- Failure-tolerance by construction: if provider X changes terms, only that component needs migration. Other components continue operating.
- This reframes sustainability as a **distributed-systems question** rather than a funding question.

**4. Demonstrating with autoBSgenome (200 words)**
- The gap in the BSgenome corner of Bioconductor:
  - 196 Bioconductor packages depend on BSgenome
  - Only 113 pre-built BSgenome packages exist on Bioconductor, covering 33 organisms
  - Over 3,500 eukaryotic reference genomes are available from NCBI and Ensembl but are not packaged
- autoBSgenome closes this gap as a demonstration of the architecture at scale.
- TSSr user feedback is cited briefly as evidence the gap has real downstream consequences, but **only as motivation**, not as a biology chapter.

---

## Methods (~1,000 words)

**M1. The compositional free-tier architecture (400 words) — PROMOTED from Methods subsection to paper-level principle**

- **Component inventory:**
  | Layer | Provider | Free-tier limit | Failure mode | Migration path |
  |---|---|---|---|---|
  | Static frontend | Cloudflare Pages | Unlimited bandwidth, 500 builds/mo | Terms change / account lock | Netlify, Vercel, GitHub Pages — same Next.js static export |
  | Edge API | Cloudflare Workers | 100k req/day | Same as above | Deno Deploy, Vercel Edge |
  | Compute | GitHub Actions | 2,000 min/mo private, unlimited for public repos | Rate change / repo archival | Cirrus CI (unlimited public), GitLab CI |
  | Artifact storage | GitHub Releases | No per-file limit on 2 GB tarballs, unlimited releases | Repo change | Zenodo (DOI-backed, permanent), Cloudflare R2 (10 GB free + zero egress) |
  | Container images | GitHub Packages (ghcr.io) | Unlimited for public repos | Same | DockerHub, Quay.io |
  | CI/CD metadata | Git + GitHub | — | Repo loss | Self-hostable (GitLab), full git mirror on any host |
  | DOI / archival | — (not yet) | Free | — | **Zenodo** for permanent DOI + archival copy |

- Explicit architectural principles:
  1. Every stateful component must have an exporter.
  2. No single provider may hold > 50% of service-critical state.
  3. All glue code is text / scripts — not provider-specific DSL.
  4. Every external API call must degrade gracefully.

**M2. autoBSgenome as the implementation (400 words)**
- System walk-through: accession in → metadata retrieval (NCBI Datasets API / Ensembl REST) → FASTA download → 2bit conversion → seed file generation → R CMD build → GitHub Release.
- Batch pipeline: cron → dispatcher → per-package dispatch → `update-repo-index.yml` sync.
- Circuit breaker, retry logic, queue state management.

**M3. Ensuring reproducibility of the architecture itself (200 words)**
- All workflow files, scripts, and container Dockerfile are in the public repo.
- Any reader can fork-and-deploy a different domain's analog (e.g., the same pattern for transcriptome annotations, variant catalogs, etc.)

---

## Results (~1,500 words)

**R1. Operational cost validation (300 words)**
- 12+ months of operation data: total cost $0. Break down by component.
- Counterfactual estimate: equivalent AWS deployment ($50-500/month depending on traffic and storage); equivalent self-hosted VPS ($10-50/month).
- **Claim:** annual operating cost is bounded by zero for the foreseeable future.

**R2. Failure-mode stress test (300 words)**
- For each component, document actual or simulated failure scenarios encountered during development and the recovery path taken. Examples:
  - GitHub Actions rate limiting → batch dispatcher circuit breaker added.
  - Ensembl FTP path changes → resolver fallback logic.
  - Merge conflicts on minified JSON → idempotent re-apply logic.
- Present these as evidence that **real-world degradation modes were encountered and handled architecturally, not by paying more**.

**R3. autoBSgenome resource coverage (500 words)**
- Final numbers (after batch completion): 3,553 BSgenome packages across 6 taxonomic divisions.
- Coverage statistics (taxonomic distribution figure).
- Benchmark across 33 genomes (smaller table than v2): median 52 s for small, 148 s for vertebrate-scale.
- Comparison with pre-existing Bioconductor 113-package inventory.
- Repository design: CRAN-like index, browse page, taxonomy tree.

**R4. Transferability demonstration (400 words) — NEW SECTION**
- Show that the architecture is not BSgenome-specific. Describe how the identical pattern could host:
  - a genome annotation repository
  - a pre-computed alignment catalog
  - a TFBS motif collection
  - any "text input → compute → artifact download" service
- One or two specific worked examples of how components would be wired.
- Argue: the **BSgenome instance is one population of a family**; the pattern is what's novel.

---

## Discussion (~800 words)

**D1. Architectural sustainability as a FAIR axis (300 words)**
- The FAIR principles (Findable, Accessible, Interoperable, Reusable) presuppose the resource still exists.
- Longevity is an implicit precondition that has no operational definition in FAIR.
- Propose "Sustainable" (the unspoken S in FAIR) as requiring **demonstrable funding-independent operation**, with the compositional free-tier architecture as one concrete instantiation.

**D2. Limitations of the pattern (200 words)**
- Honest about what this architecture can't do:
  - Large datasets that exceed free-tier storage (needs R2 or Zenodo tier).
  - Services requiring persistent state beyond what KV/D1 offers.
  - Workloads exceeding 2,000 min/mo on private repos.
- Explicit: the pattern trades engineering effort for zero operating cost.

**D3. Broader implications for publishing bioinformatics software (200 words)**
- Journals and funders increasingly ask for "data availability" and "software availability" statements.
- Add an implicit fourth: "operational availability" — how the service will remain accessible beyond the grant.
- Suggest that editors/reviewers can begin asking for architectural sustainability plans as part of software/database papers.

**D4. Future extensions (100 words)**
- Zenodo-backed DOI minting for each release.
- Community contribution pipeline.
- R-universe integration.

---

## Figures and tables

**F1. Compositional architecture diagram** — layers, providers, data flow, failure-tolerance boundaries
**F2. Tool longevity evidence figure** — meta-analysis of prior work on bioinformatics tool lifespan
**F3. Cost comparison figure** — autoBSgenome $0 vs counterfactual AWS and VPS
**F4. Resource coverage figure** — taxonomic breadth of the 3,553 packages
**F5. Transferability schematic** — how the same architecture adapts to 2-3 other service types

**T1. Component inventory table** (Methods M1) — migration paths matrix
**T2. BSgenome benchmark** (Results R3) — 33-genome benchmark (kept from v2)
**T3. BSgenome Bioconductor dependents** (Results R3) — 196-package census (kept from v2)

---

## Where this differs from v2 draft

| v2 had | v3 Plan C has |
|---|---|
| "A web tool that builds BSgenome packages" | "An architectural pattern for sustainable services, demonstrated via BSgenome" |
| Tool-paper framing | Problem-solution methodology paper framing |
| Architecture as Methods subsection | Architecture as paper-level thesis |
| Cost mentioned briefly | Full cost + failure-mode + transferability sections |
| Limitations noted casually | "Sustainable" proposed as missing FAIR axis |
| Benchmarks are the centerpiece | Benchmarks are supporting evidence |

---

## Pre-submission checklist (after advisor sign-off)

- [ ] Literature review on bioinformatics tool longevity (Wren 2016 already cited; need Mangul et al., Kim et al., Schultheiss et al., etc.)
- [ ] Quantitative cost counterfactual (need realistic AWS estimate for the equivalent workload)
- [ ] Failure-mode table with real incidents + resolutions from git history
- [ ] Transferability worked examples (2-3 concrete alternate services)
- [ ] F1 architecture diagram (clean version)
- [ ] F3 cost comparison figure
- [ ] Post to bioRxiv
- [ ] NARGAB cover letter including explicit fee-waiver request if relevant

---

## Open questions for advisor

1. Is "compositional free-tier architecture as a FAIR axis" a defensible claim or an oversell?
2. Should we pair with a co-author PI who can potentially underwrite APC, or prioritize independent submission with waiver request?
3. Should autoBSgenome also be submitted separately as a stand-alone Bioconductor-adjacent tool, or is this paper sufficient?
4. How aggressive should we be about "this pattern should change how software papers are reviewed"? (D3 tone)
