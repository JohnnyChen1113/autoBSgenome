# autoBSgenome
A python warp of BSgenome. Build BSgenome like filling in a questionnaire!

You also can try [BSgenomeForge](https://github.com/Bioconductor/BSgenomeForge), but it have some bug:
1. It cannot deal with ambiguous nucleotides in sequence (like Y means C or T, M means A or C, FYI: [IUPAC Codes](https://www.bioinformatics.org/sms/iupac.html))
2. It will verify the genome information with NCBI, but the information it gets is always the latest version, not the input version you used.

In these cases, you can try autoBSgenome.
It will generate the xx file for you!
