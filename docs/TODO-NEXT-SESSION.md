# TODO — Remaining Tasks

## DONE (this session)
- ~~Fix "Other" group~~ → Now uses NCBI Taxonomy hierarchy
- ~~Key-value display~~ → Assembly, Provider, Accession, Version, Size labeled
- ~~FASTA sequence ID preview~~ → Build pipeline extracts headers
- ~~Taxonomy tree browse page~~ → Like BUSCO lineage, collapsible
- ~~Auto-taxonomy for new builds~~ → Index updater queries NCBI Taxonomy API
- ~~Paper v2~~ → Reframed for MGG, addressed GPT review
- ~~References verified~~ → APA 7, 4 errors corrected
- ~~Batch build loop started~~ → 15/30min, ~14 days for 10,177 genomes

## Still TODO

### High Priority
1. **Alphabet quick filter** — A-Z bar at top of browse page for genus first letter
2. **Update paper v2 with corrected references** — Fix the 4 errors in draft-v2.md
3. **Agent integration hardening** — Add a generated OpenAPI contract and a dedicated structured search endpoint; the standards-compliant installable Agent Skill now lives at `skills/autobsgenome/`

### Medium Priority
4. **Interactive D3.js taxonomy tree** — Separate /tree page, full visualization
5. **Ensembl batch builds** — After NCBI RefSeq is done
6. **Build progress dashboard** — Show X/10177 done, ETA
7. **Batch build: mark done after completion** — Currently marks building but not done

### Lower Priority
8. **OpenAPI-driven API docs** — Replace hand-maintained examples with a schema-generated reference
9. **Copy-to-clipboard for all code blocks** — R commands on browse page
10. **CF Pages unification** — Move browse page from GitHub Pages to CF Pages
11. **Zenodo integration** — For genomes >2 GB
