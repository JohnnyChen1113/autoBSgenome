PROMPT_TEXTS = {
    "package": """
# (1/15) Package Name
**Required**: The unique identifier for your BSgenome package.

**Naming Convention** (4 parts separated by dots):
```
BSgenome.{Organism}.{Provider}.{Version}
```

**Rules**:
- **Part 1**: Always starts with `BSgenome.` (required)
- **Part 2**: Abbreviated organism name
  - Format: First letter of genus (uppercase) + species name (lowercase)
  - Examples: `Hsapiens` (Homo sapiens), `Mmusculus` (Mus musculus), `Athaliana` (Arabidopsis thaliana)
- **Part 3**: Data provider (UCSC, NCBI, Ensembl, etc.)
- **Part 4**: Assembly version identifier
  - UCSC format: `hg38`, `mm10`, `rn6`
  - NCBI format: `GRCh38`, `GRCm39`, `TAIR10`

**Complete Examples**:
- `BSgenome.Hsapiens.UCSC.hg38` (Human genome from UCSC)
- `BSgenome.Mmusculus.NCBI.GRCm39` (Mouse genome from NCBI)
- `BSgenome.Scerevisiae.UCSC.sacCer3` (Yeast genome)

**Common Mistakes to Avoid**:
❌ Missing `BSgenome.` prefix
❌ Using spaces instead of dots
❌ Capitalizing entire organism name
""",

    "title": """
# (2/15) Package Title
**Required**: A human-readable description of your package (max 65 characters recommended).

**Format**:
```
Full genome sequences for {Organism} ({Provider} version {Assembly})
```

**Examples**:
- `Full genome sequences for Homo sapiens (UCSC version hg38)`
- `Full genome sequences for Mus musculus (NCBI version GRCm39)`
- `Full genome sequences for Arabidopsis thaliana (TAIR version 10)`

**Guidelines**:
✓ Use Title Case (capitalize principal words)
✓ Include organism scientific name
✓ Specify provider and version
✓ Keep under 65 characters when possible
✗ Don't end with a period
✗ Don't repeat the package name
✗ Don't start with "This package" or "A package"

**Tips**:
- For subspecies, include the full name: "Homo sapiens neanderthalensis"
- For strain-specific genomes, add strain info: "Escherichia coli K-12"
""",

    "description": """
# (3/15) Package Description
**Optional but Recommended**: A detailed explanation of the genome data (single paragraph).

**What to Include**:
- Genome assembly details (assembly name, release date)
- Data source and provider
- Any special characteristics (if applicable)
- Sequencing project or consortium name (if relevant)

**Good Examples**:

*For Human*:
"Full genome sequences for Homo sapiens as provided by UCSC (hg38, Dec. 2013) based on assembly GRCh38.p14 from the Genome Reference Consortium."

*For Model Organism*:
"Full genome sequences for Saccharomyces cerevisiae (Yeast) as provided by UCSC (sacCer3, April 2011) based on SGD assembly."

*For Plant*:
"Full genome sequences for Arabidopsis thaliana as provided by TAIR (TAIR10, Nov. 2010), the reference genome for plant biology research."

**Guidelines**:
✓ Write complete sentences
✓ Be informative but concise
✓ Use double quotes for publications/titles
✓ Use single quotes for software names
✗ Don't use multiple paragraphs
✗ Don't start with the package name

**If unsure**: Leave blank - the title will be used as fallback.
""",

    "version": """
# (4/15) Package Version
**Required**: Version number for your package (use semantic versioning).

**Format**: `MAJOR.MINOR.PATCH` (e.g., `1.0.0`)

**Common Choices**:
- `1.0.0` - First stable release (recommended for new packages)
- `0.1.0` - Initial development version
- `1.4.2` - Mature package with updates

**Version Number Rules**:
- At least 2 numbers required (e.g., `1.0`)
- Usually 3 numbers (e.g., `1.0.0`)
- Numbers separated by `.` or `-`
- All numbers must be non-negative integers

**Important Notes**:
⚠ Version comparison: `0.9 < 0.75` (because 9 < 75)
⚠ Leading zeros normalized: `0.01.0` becomes `0.1-0`

**When to Increment**:
- **Major** (X.0.0): New assembly version
- **Minor** (1.X.0): Annotation updates, metadata fixes
- **Patch** (1.0.X): Bug fixes, documentation

**Recommendation**: Start with `1.0.0` for most users.
""",

    "organism": """
# (5/15) Organism Scientific Name
**Required**: The taxonomic scientific name using binomial nomenclature.

**Format**: `Genus species` or `Genus species subspecies`

**Standard Examples**:
- `Homo sapiens` (Human)
- `Mus musculus` (Mouse)
- `Drosophila melanogaster` (Fruit fly)
- `Arabidopsis thaliana` (Thale cress)
- `Saccharomyces cerevisiae` (Baker's yeast)
- `Caenorhabditis elegans` (Roundworm)

**With Subspecies/Strain**:
- `Homo sapiens neanderthalensis` (Neanderthal)
- `Mus musculus domesticus` (Western European house mouse)
- `Escherichia coli K-12` (E. coli strain K-12)

**Rules**:
✓ Capitalize genus name (first word)
✓ Lowercase species and subspecies names
✓ Use Latin/scientific names only
✓ Check NCBI Taxonomy Database for correct spelling

**Where to Find**:
- NCBI Taxonomy: https://www.ncbi.nlm.nih.gov/taxonomy
- Look in your FASTA file header
- Check the genome assembly page

**Common Mistakes**:
❌ Using common names: "Human" → ✓ "Homo sapiens"
❌ All lowercase: "homo sapiens" → ✓ "Homo sapiens"
❌ Wrong capitalization: "Homo Sapiens" → ✓ "Homo sapiens"
""",

    "common_name": """
# (6/15) Common Name
**Required**: The widely-used common name in English.

**Examples by Organism**:

**Mammals**:
- `Human` (Homo sapiens)
- `Mouse` (Mus musculus)
- `Rat` (Rattus norvegicus)
- `Cow` (Bos taurus) *[or "Bovine"]*
- `Dog` (Canis familiaris)

**Model Organisms**:
- `Yeast` (Saccharomyces cerevisiae)
- `Worm` (Caenorhabditis elegans)
- `Fly` (Drosophila melanogaster)
- `Zebrafish` (Danio rerio)

**Plants**:
- `Thale cress` (Arabidopsis thaliana)
- `Rice` (Oryza sativa)
- `Maize` (Zea mays)

**Microorganisms**:
- `E. coli` (Escherichia coli)
- `Baker's yeast` (Saccharomyces cerevisiae)

**Guidelines**:
✓ Choose ONE common name if multiple exist
✓ Use the most widely recognized name
✓ Capitalize appropriately (generally title case)
✗ Avoid abbreviations unless standard (like "E. coli")

**For Multiple Names**: Pick the most commonly used in scientific literature.
- Bos taurus: "Cow" is more common than "Bovine"
- Caenorhabditis elegans: "Worm" or "C. elegans" both acceptable
""",

    "genome": """
# (7/15) Genome Assembly Identifier
**Required**: The official assembly version/identifier.

**Important**: This should match **Part 4** of your package name!

**NCBI Assembly Format**:
- Human: `GRCh38.p14`, `GRCh37`
- Mouse: `GRCm39`, `GRCm38`
- Rat: `mRatBN7.2`
- Format: Usually `[Project][Version]` or `[Accession]`

**UCSC Genome Format**:
- Human: `hg38`, `hg19`
- Mouse: `mm39`, `mm10`
- Rat: `rn7`, `rn6`
- Yeast: `sacCer3`
- Format: [species code][version number]

**Other Databases**:
- Ensembl: `GRCh38`, `GRCm39`
- TAIR (Arabidopsis): `TAIR10`, `TAIR9`
- WormBase: `WBcel235`
- FlyBase: `BDGP6`

**Where to Find**:
- NCBI: Look for "Assembly name" on assembly page
- UCSC: Check the genome browser URL (e.g., genome.ucsc.edu/cgi-bin/hgGateway?db=hg38)
- In FASTA filename: often included like `GCF_000001405.40_GRCh38.p14`

**Examples**:
- Package: `BSgenome.Hsapiens.UCSC.hg38` → Genome: `hg38`
- Package: `BSgenome.Mmusculus.NCBI.GRCm39` → Genome: `GRCm39`

**Tip**: This field will auto-suggest based on your package name (Part 4).
""",

    "provider": """
# (8/15) Genome Data Provider
**Required**: Organization that published/maintains this genome assembly.

**Important**: Should match **Part 3** of your package name!

**Common Providers**:

**General Databases**:
- `UCSC` - UC Santa Cruz Genome Browser (most user-friendly)
- `NCBI` - National Center for Biotechnology Information
- `Ensembl` - European genome database

**Organism-Specific**:
- `TAIR` - The Arabidopsis Information Resource (plants)
- `FlyBase` - Drosophila genome database
- `WormBase` - C. elegans genome database
- `SGD` - Saccharomyces Genome Database (yeast)
- `BDGP` - Berkeley Drosophila Genome Project

**Institution-Specific**:
- Custom lab assemblies: Use institution abbreviation

**Examples**:
- Downloaded from UCSC Genome Browser → `UCSC`
- Downloaded from NCBI Assembly → `NCBI`
- Downloaded from FlyBase → `FlyBase`

**How to Determine**:
1. Check where you downloaded your FASTA file
2. Look at the assembly page URL
3. Check FASTA headers for source information

**Tip**: This field will auto-suggest based on your package name (Part 3).
""",

    "release_date": """
# (9/15) Assembly Release Date
**Required**: When this genome assembly was officially released.

**Format**: `Mon. YYYY` (abbreviated month with period, space, year)

**Correct Examples**:
- `Apr. 2011`
- `Dec. 2013`
- `Jun. 2020`
- `Feb. 2017`

**Month Abbreviations**:
Jan. Feb. Mar. Apr. May Jun. Jul. Aug. Sep. Oct. Nov. Dec.

**Where to Find the Date**:

**NCBI**:
- Assembly page → Look for "Submission date" or "Release date"
- Example: https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.40/

**UCSC**:
- Genome browser → Gateway page shows "Release date"
- Or check: http://hgdownload.soe.ucsc.edu/goldenPath/{genome}/

**In FASTA Files**:
- Sometimes in header comments
- Check README files in download directory

**If Exact Date Unknown**:
- Use the year the assembly was published
- Format: `Jan. 2020` (use first month of year)
- Can check associated publications for release year

**Default Suggestion**: Today's date is pre-filled, but you should change it to the actual assembly release date.

**Example**:
- GRCh38 (hg38) released December 2013 → `Dec. 2013`
""",

    "source_url": """
# (10/15) Source URL
**Optional**: Direct link to where the genome data can be downloaded.

**Purpose**:
- Provides traceability and reproducibility
- Helps others access the same data
- Documents data provenance

**Recommended Format by Provider**:

**NCBI Assembly**:
```
https://www.ncbi.nlm.nih.gov/assembly/GCF_XXXXXXXXX.X/
```
Example: `https://www.ncbi.nlm.nih.gov/assembly/GCF_000001405.40/`

**UCSC Genome**:
```
http://hgdownload.soe.ucsc.edu/goldenPath/{genome}/bigZips/
```
Example: `http://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/`

**Ensembl**:
```
http://ftp.ensembl.org/pub/release-{version}/fasta/{species}/
```
Example: `http://ftp.ensembl.org/pub/release-109/fasta/homo_sapiens/`

**Tips**:
✓ Use the landing page URL (not direct file link)
✓ Use permanent/stable URLs
✓ Prefer HTTPS when available
✗ Don't use temporary download links
✗ Don't use file-specific URLs that may change

**If You Don't Know**:
- Leave blank - this field is optional
- You can add it later if needed
- Not critical for package functionality

**Why This Matters**:
Helps users verify data origin and cite sources correctly.
""",

    "organism_biocview": """
# (11/15) Organism BiocView Term
**Optional**: Bioconductor's standardized organism term (for repository submission).

**Purpose**: Used only if you plan to submit to Bioconductor repository.

**Format**: Scientific name with underscores instead of spaces.

**Common Examples**:
- `Homo_sapiens` (Human)
- `Mus_musculus` (Mouse)
- `Drosophila_melanogaster` (Fly)
- `Arabidopsis_thaliana` (Arabidopsis)
- `Saccharomyces_cerevisiae` (Yeast)
- `Caenorhabditis_elegans` (Worm)

**How to Generate**:
1. Take your organism field (e.g., "Homo sapiens")
2. Replace spaces with underscores (e.g., "Homo_sapiens")

**Where This Appears**:
- Determines placement in Bioconductor's organism tree
- See: https://bioconductor.org/packages/release/BiocViews.html#___Organism

**When to Use**:
✓ Planning to submit to Bioconductor
✓ Want proper categorization in repositories

**When to Skip**:
✗ Personal/local use only
✗ Internal lab package
✗ Not submitting to public repository

**Important Note**:
This is the ONLY field that doesn't get stored in the actual BSgenome object - it's only used for repository metadata.

**If Unsure**: Leave blank or use the underscore format of your organism name.
""",

    "BSgenomeObjname": """
# (12/15) BSgenome Object Name
**Required**: The R object name when the package is loaded.

**Important**: Should match **Part 2** of your package name!

**Examples**:
- Package: `BSgenome.Hsapiens.UCSC.hg38` → Object: `Hsapiens`
- Package: `BSgenome.Mmusculus.NCBI.GRCm39` → Object: `Mmusculus`
- Package: `BSgenome.Athaliana.TAIR.TAIR10` → Object: `Athaliana`

**What This Means**:
When users load your package in R, they access the genome via:
```r
library(BSgenome.Hsapiens.UCSC.hg38)
genome <- BSgenome.Hsapiens.UCSC.hg38::Hsapiens
# Or simply:
genome <- Hsapiens
```

**Naming Rules**:
✓ Same as Part 2 of package name
✓ No dots or special characters
✓ CamelCase format
✓ Genus letter capitalized + species lowercase

**Common Patterns**:
- Homo sapiens → `Hsapiens`
- Mus musculus → `Mmusculus`
- Arabidopsis thaliana → `Athaliana`
- Saccharomyces cerevisiae → `Scerevisiae`

**Tip**: This field will auto-suggest based on your package name (Part 2).
""",

    "circ_seqs": """
# (13/15) Circular Sequences
**Usually Optional**: Specifies which sequences are circular (e.g., mitochondria, plasmids).

**When You Can Skip This**:
✓ Your genome is registered in GenomeInfoDb (most NCBI/UCSC genomes)
✓ The system will auto-detect circular sequences
✓ Recommended: Leave blank unless you know it's needed

**When You Need This**:
- Custom/novel genome assemblies
- Non-model organisms not in GenomeInfoDb
- Special plasmid or organellar sequences

**Common Values**:

**For Mammals** (mitochondrial DNA):
```r
"chrM"
```

**For Yeast** (with 2-micron plasmid):
```r
c("chrM", "2micron")
```

**No Circular Sequences**:
```r
character(0)
```

**For Bacteria** (chromosome + plasmids):
```r
c("chromosome", "plasmid1", "plasmid2")
```

**Important Notes**:
- Use R syntax (this is an R expression)
- Sequence names must EXACTLY match your FASTA headers
- For single value, use quotes: `"chrM"`
- For multiple values, use `c()`: `c("chrM", "plas1")`

**How to Check Your FASTA**:
```bash
grep ">" your_genome.fasta | head
```
Look for sequence names like:
- `>chrM` (mitochondrial)
- `>MT` (alternative mitochondrial notation)
- `>2micron` (yeast plasmid)

**Default Recommendation**:
Leave blank - the system usually handles this automatically.
""",

    "seqs_srcdir": """
# (14/15) Sequences Source Directory
**Required**: Full path to the folder containing your genome sequence file.

**What to Enter**:
The **absolute path** (not relative) to the directory where your FASTA or 2bit file is located.

**Current Directory**: {current_dir}

**Examples**:

**Linux/Mac**:
```
/home/username/genomes/hg38
/data/assemblies/mouse/GRCm39
/Users/lab/Desktop/genome_data
```

**Windows** (if applicable):
```
C:/Users/username/Documents/genomes
D:/data/assemblies
```

**Recommendations**:
✓ Use absolute paths (start with `/` on Linux/Mac)
✓ Avoid spaces in path names
✓ Use a dedicated directory for each genome
✓ Keep backup of original FASTA files

**Tip**:
The current working directory is shown above and will be suggested as default. Press ENTER to use it, or type a different path.

**What Happens Next**:
- Your FASTA file will be converted to 2bit format in this directory
- The BSgenome package will reference files from this location
- Make sure you have write permissions in this directory

**Verification**:
After entering, you'll see a list of FASTA files found in this directory to help you confirm you're in the right place.
""",

    "seqfile_name": """
# (15/15) Sequence File Name
**Required**: Name of your genome sequence file.

**Supported Formats**:
- `.fasta` / `.fa` - FASTA format (will be auto-converted to 2bit)
- `.fna` - NCBI FASTA format (will be auto-converted)
- `.fas` - Alternative FASTA format (will be auto-converted)
- `.2bit` - Already in 2bit format (used directly)

**What You'll See**:
A list of all FASTA/2bit files in your source directory will be displayed above to help you choose.

**Examples**:
```
GCF_000001405.40_GRCh38.p14_genomic.fna
Homo_sapiens.GRCh38.dna.primary_assembly.fa
hg38.fa.gz
mm39_genome.fasta
my_genome.2bit
```

**Important Notes**:
⚠ **FASTA files will be automatically converted** to 2bit format
- Original FASTA file will be preserved
- Conversion may take several minutes for large genomes
- 2bit format is more efficient for BSgenome packages

✓ **If you already have a .2bit file**, enter its name directly
- No conversion needed
- Faster package creation

**File Requirements**:
- Must be in the source directory (previous step)
- Must be uncompressed (or .gz compressed)
- Should contain all chromosomes/contigs
- Headers should follow standard format (>chr1, >chrX, etc.)

**Tips**:
- For compressed files (.gz), they'll be handled automatically
- Make sure chromosome names match your assembly (chr1 vs Chr1 vs 1)
- Verify file integrity before proceeding (no truncation/corruption)

**What Happens**:
1. If FASTA: Converted to {name}.2bit in same directory
2. If 2bit: Used directly for package creation
3. Output will be shown during conversion process
"""
}

# Note: The {current_dir} placeholder in seqs_srcdir should be replaced at runtime
