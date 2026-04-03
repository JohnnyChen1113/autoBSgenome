# TODO — Next Session

## URGENT — Browse Page Bugs & Improvements

### 0a. Fix "Other" group — new packages missing taxonomy group
- `update-repo-index.yml` doesn't pass `group` field
- Need to either: pass group from build workflow, or look it up from build-queue.json in the index updater
- All 12 newly batch-built packages show as "Other" instead of proper kingdom

### 0b. Key-value display in package cards
- Current: `GSC_Weel_1.0 · NCBI · v1.0.0 · 143.0 MB · GCF_004355925.1 ↗`
- Should be: `Assembly: GSC_Weel_1.0 | Provider: NCBI | Version: 1.0.0 | Package size: 143.0 MB | Accession: GCF_004355925.1`
- Users can't tell what each value means without labels

### 0c. FASTA sequence ID preview
- Show first 3 FASTA headers (e.g., `>NC_047562.1`, `>chr1`) in each package card
- This tells users whether the sequence IDs match their BAM/BED files
- Requires: extracting headers during build, storing in packages.json metadata
- Build pipeline change: after faToTwoBit, run `head -n 100 genome.fa | grep "^>" | head -3`

### 0d. Update paper v2 with corrected references
- Fix 4 reference errors found by verification (see paper/references-apa7.md)

## API & Skills

### 1. Claude Code / Claw Skill
Create a skill that lets AI coding tools directly build and install BSgenome packages:
```
User: "I need BSgenome for Takifugu flavidus"
AI: [calls AutoBSgenome API] → builds → installs in R
```
- Skill file: describe the API endpoints and how to use them
- Trigger: when user mentions BSgenome, genome package, or specific organism
- Flow: fetch accession from NCBI → call /api/build → poll /api/status → install

### 2. MCP Server
Build an MCP server so Claude Code can natively call AutoBSgenome:
- `build_bsgenome(accession)` → triggers build, returns download URL
- `search_bsgenome(organism)` → searches the community repo
- `install_bsgenome(package_name)` → generates R install command

### 3. Public API Documentation Page
- Add `/api` route on autobsgenome.pages.dev with interactive API docs
- Try-it-out forms for each endpoint
- Code examples in curl, R, Python

## Browse Page Improvements

### 4. Alphabet Quick Filter
- A-Z letter bar at top of browse page
- Click a letter to filter organisms by genus first letter
- Highlight letters that have organisms

### 5. Interactive Taxonomy Tree
- Separate `/tree` page with D3.js collapsible tree
- Data from NCBI Taxonomy API
- Green nodes = BSgenome available, Gray = not yet built
- Click gray node → "Build this in 1 minute!" link to build page
- Searchable

### 6. Browse Page Polish
- Show common name more prominently
- Add genome size (bp) alongside package size (MB)
- FASTA sequence ID preview (first 3 headers)
- Link to Bioconductor for organisms that have official BSgenome

## Build Pipeline

### 7. Monitor Batch Progress
- Dashboard showing: X done / Y total, estimated completion date
- Could be a simple page on gh-pages updated by batch workflow

### 8. Ensembl Batch Builds
- After NCBI RefSeq is done, do Ensembl genomes too
- Different FASTA naming convention — important for users

### 9. Build Deduplication
- Before building, check if pkg- release already exists → skip
- Handle version updates (new assembly version for same organism)

## Paper

### 10. Update Draft
- Add batch build results (X organisms built in Y days)
- Add browse page screenshots
- Update performance numbers with real data
- Add taxonomy tree as a figure
