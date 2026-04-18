# autoBSgenome Paper — Three Framings (saved for advisor discussion)

**Date:** 2026-04-18
**Target journal:** NAR Genomics & Bioinformatics (NARGAB)
**Preprint:** bioRxiv first, before journal submission
**Funding strategy:** await co-author contribution / fee waiver / next-grant retroactive

All three framings are saved; we can pivot between them after discussion with advisor.

---

## Shared context

- The paper's two raw deliverables are (i) a comprehensive BSgenome resource covering 3,553 eukaryotic reference genomes (NCBI 837 + Ensembl 2,716), and (ii) a deliberately designed zero-marginal-cost serverless architecture (Cloudflare Pages + Workers + GitHub Actions + GitHub Releases).
- autoBSgenome is a web **service** that wraps BSgenome + BSgenomeForge — it is NOT itself a Bioconductor R package. This rules out Bioconductor package submission as a paper deliverable.
- The open intellectual tension: is this paper primarily "we built a resource" or "we solved tool longevity"? The three framings below allocate emphasis differently.

---

## Framing A — BSgenome resource primary, architecture secondary

**Split:** resource 70% / architecture 20% / conclusion 10%

**Thesis:** "An openly accessible BSgenome repository covering the eukaryotic tree of life."

**Structure:**
- Abstract leads with the coverage gap (33 → 3,553 species).
- Methods describes the build pipeline in technical detail; the serverless architecture is a subsection.
- Results dominated by coverage statistics, benchmarks, repository organization.
- Discussion has one subsection on "sustainable architecture" as context.

**Pros:**
- Straightforward match to NARGAB's "database/resource paper" slot.
- Low risk of scope creep; deliverable is concrete and countable.
- The batch-build numbers (3,553 packages, taxonomic breadth) do the heavy lifting.

**Cons:**
- Reads as "yet another tool/resource paper." Memorability low.
- Reviewers will focus on coverage breadth and benchmark rigor, not novelty.
- The architectural insight gets buried where no one cites it.

---

## Framing B — 50/50 dual thesis

**Split:** resource 50% / architecture 50%

**Thesis:** "A zero-cost sustainable infrastructure for systematically closing the BSgenome accessibility gap."

**Structure:**
- Abstract names both contributions in parallel.
- Two co-equal Results sections: resource coverage + architecture/sustainability.
- Discussion integrates both as inseparable.

**Pros:**
- Honors both contributions without subordinating either.
- The resource validates the architecture; the architecture explains how the resource stays alive.

**Cons:**
- Dual-thesis papers often read unfocused to reviewers ("what is this paper really about?").
- Harder to defend in 6,000 words than a single-thesis paper.
- Risk of neither thesis being developed deeply enough.

---

## Framing C — Architecture primary, autoBSgenome as working exemplar [RECOMMENDED FOR DRAFTING]

**Split:** architecture 60% / resource (BSgenome) 40%

**Thesis:** "Compositional use of multiple providers' free tiers enables bioinformatics resources to be both built and perpetually maintained at zero marginal cost. We demonstrate this architecture through autoBSgenome, which systematically closes the BSgenome accessibility gap for 3,553 eukaryotic reference genomes."

**Structure:**
- Paper opens with the **tool longevity crisis** as the problem: documented evidence that bioinformatics tools/databases have median lifespan ≈ 5 years, with failure causes concentrated in funding/personnel discontinuities (cite Wren 2016, Mangul et al. 2019, others).
- Core claim: sustainability must be **designed into the architecture**, not hoped for. Presents the "compositional free-tier" pattern as a design principle.
- **autoBSgenome is the exemplar** — it's not the paper's subject so much as the existence proof. The 3,553-package resource demonstrates that the pattern scales beyond toy examples.
- Results include:
  - Resource coverage (same as A, but as validation of architecture)
  - **Quantitative cost analysis** ($0/month operating cost; counterfactual estimates for traditional server-based deployment)
  - **Failure mode → migration path matrix** (what happens if each provider changes terms)
  - **Transferability case** — the pattern applies to databases, tools, or any "compute + static resource" service
- Discussion argues for architectural sustainability as an underappreciated component of FAIR principles.

**Pros:**
- Solves a problem the whole field has but rarely names.
- Citable from outside the BSgenome niche — anyone building bioinformatics services can cite this as prior art for sustainable design.
- Intellectually more novel; problem-solution narrative is the strongest form in methodology papers.
- NARGAB explicitly welcomes methodology/infrastructure contributions.
- **User's instinct matches:** "C solves a long-term pain point and then proposes a solution."

**Cons / risks:**
- The architectural claim has to be **defensible**, not rhetorical. Requires:
  - Documented evidence of the tool longevity problem (literature review).
  - Concrete failure modes with concrete migration paths for each.
  - Quantified cost analysis with counterfactuals.
  - Transferability framework that survives "so what if you only tested this on BSgenome?"
- Harder to write well. One weak point (e.g., hand-wavy cost comparison) and the paper collapses to a glorified A.
- Reviewers may push: "isn't this just an engineering blog post in paper form?" — need careful academic framing.

---

## Decision log

- 2026-04-18: User rejected earlier "biological case study" framings (TSSr usage, motif comparison) — those drift away from BSgenome itself.
- 2026-04-18: User rejected MGG as target ("硬凹"); switched to NARGAB + bioRxiv preprint.
- 2026-04-18: User's preference order: C > A >> B.
- Pending: advisor discussion to finalize A vs C.
