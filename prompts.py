PROMPT_TEXTS = {
    "package": """
# (1/15) Package Information
**Package**: Name to give to the target package.

The convention used for the packages built by the Bioconductor project is to use a name made of 4 parts separated by a dot.

- **Part 1** is always `BSgenome.`
- **Part 2** is the abbreviated name of the organism (when the name of the organism is made of 2 words, we put together the first letter of the first word in upper case followed by the entire second word in lower case e.g. `Rnorvegicus`).
- **Part 3** is the name of the organisation who provided the genome (e.g. `UCSC` or `NCBI`).
- **Part 4** is the release string or number used by this organisation to identify this version of the genome (e.g. `rn4` or ).
""",
    "title": """
# (2/15) Title: The title of the target package
**Example**: Full genome sequences for Rattus norvegicus (UCSC version rn4)
- Give a short description of the package. Some package listings may truncate the title to 65 characters.

- It should use title case (that is, use capitals for the principal words: tools::toTitleCase can help you with this), not use any markup, not have any continuation lines, and not end in a period (unless part of …).

- Do not repeat the package name: it is often used prefixed by the name.

- Refer to other packages and external software in single quotes, and to book titles (and similar) in double quotes.
""",
    "description": """
# (3/15) Description

Give a comprehensive description of what the package does.

`(optional! You can just left it blank if you have no idea how to set it)`

- One can use several (complete) sentences, but only one paragraph.
- It should be intelligible to all the intended readership (e.g. for a CRAN package to all CRAN users).
- It is good practice not to start with the package name, ‘This package’ or similar.
- As with the ‘Title’ field, double quotes should be used for quotations (including titles of books and articles), and single quotes for non-English usage, including names of other packages and external software.
- This field should also be used for explaining the package name if necessary.
""",
    "version": """
# (4/15) Version information
gives the version of the package.
- This is a sequence of at least two (and usually three) non-negative integers separated by single ‘.’ or ‘-’ characters.
- The canonical form is as shown in the example, and a version such as `‘0.01’` or `‘0.01.0’` will be handled as if it were **‘0.1-0’**.
- It is not a decimal number, so for example 0.9 < 0.75 since 9 < 75.
""",
    "organism": """
# (5/15) Organism information
The **scientific name** of the organism in the format Genus species (e.g. Triticum aestivum, Homo sapiens) or Genus species subspecies (e.g. Homo sapiens neanderthalensis).
""",
    "common_name": """
# (6/15) Common name information
The **common name** of the organism (e.g. Rat or Human). For organisms that have **more than one** commmon name (e.g. Bovine or Cow for Bos taurus), choose one.
""",
    "genome": """
# (7/15) Genome information
The name of the genome. 
- Typically the name of an NCBI assembly (e.g. GRCh38.p12, WBcel235, TAIR10.1, ARS-UCD1.2, etc...) or UCSC genome (e.g. hg38, bosTau9, galGal6, ce11, etc...). 
- Should preferably match part 4 of the package name (field Package).
""",
    "provider": """
# (8/15) Provider information
The provider of the sequence data files e.g. UCSC, NCBI, BDGP, FlyBase, etc... 
- Should preferably match part 3 of the package name (field Package).
""",
    "release_date": """
# (9/15) Release date information
When this assembly of the genome was released in MM. YYYY format. 
- e.g.:Apr. 2011
""",
    "source_url": """
# (10/15) Source URL information

`(optional! You can just left it blank if you have no idea how to set it)`

The permanent URL where the sequence data files used to forge the target package can be found. 
- If the target package is for an NCBI assembly, use the link to the NCBI landing page for the assembly 
- e.g. https://www.ncbi.nlm.nih.gov/assembly/GCF_003254395.2/
""",
    "organism_biocview": """
# (11/15) Organism biocview information

`(optional! You can just left it blank if you have no idea how to set it)`

The official biocViews term for this organism. 
- This is generally the same as the organism field except that spaces should be replaced with underscores. 
- The value of this field matters only if the target package is going to be added to a Bioconductor repository, 
because it will determine where the package will show up in the biocViews tree(https://bioconductor.org/packages/release/BiocViews.html#___Organism). 
- **Note that this is the only field in this category that won't get stored in the BSgenome object that will get wrapped in the target package.**
""",
    "BSgenomeObjname": """
# (12/15) BSgenomeObjname information
Should match part 2 of the package name (see Package field above).
""",
    "circ_seqs": """
# (13/15) circ_seqs information
Not needed if your NCBI assembly or UCSC genome is registered in the GenomeInfoDb package. 
- An R expression returning the names of the circular sequences (in a character vector). 
- If the seqnames field is specified, then circ_seqs must be a subset of it. E.g. "chrM" for rn4 or c("chrM", "2micron") for the sacCer2 genome (Yeast) from UCSC. 
- If the assembly or genome has no circular sequence, set circ_seqs to `character(0)`
""",
    "seqs_srcdir": """
# (14/15) seqs_srcdir information
The absolute path to the folder containing the sequence data files.
""",
    "seqfile_name": """
# (15/15) seqfile_name information
Required if the sequence data files is a single twoBit file. 
`If you dot have a twoBit file, just input a fasta file name, I will automatic cover it to .2bit format for you!`
"""
}