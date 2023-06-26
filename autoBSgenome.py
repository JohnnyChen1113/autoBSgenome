#!/usr/bin/env python
import os

if os.system('which faToTwoBit >/dev/null 2>&1') == 0:
    print('faToTwoBit is already installed.')
else:
    answer = input('faToTwoBit is not found. Do you want to download and install it? (yes/no) ').strip().lower()
    if answer == 'yes':
        print('Downloading faToTwoBit...')
        os.system('curl -O http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit')
        os.system('chmod +x faToTwoBit')
        os.system('sudo mv faToTwoBit /usr/local/bin/')
        print('faToTwoBit has been installed successfully.')
    else:
        print('faToTwoBit is not installed.')

# Prompt user for package information
print('====================(1/15)==============================')
print("""
Package: Name to give to the target package. 
The convention used for the packages built by the Bioconductor project is to use a name made of 4 parts separated by a dot. 
Part 1 is always BSgenome. 
Part 2 is the abbreviated name of the organism (when the name of the organism is made of 2 words, we put together the first letter of the first word in upper case followed by the entire second word in lower case e.g. Rnorvegicus). 
Part 3 is the name of the organisation who provided the genome (e.g. UCSC). 
Part 4 is the release string or number used by this organisation to identify this version of the genome (e.g. rn4).
""")
print('==================================================')
package_name = input("Please enter the package name: ").strip()

# Check if the package name is valid
valid_package = True
parts = package_name.split(".")
if len(parts) != 4 or parts[0] != "BSgenome":
    valid_package = False
    print("Not vaild name! Please start with 'BSgenome'!")
if not valid_package:
    print("The package name is not valid.")
else:
    print("The package name is valid.")

# Prompt user for title information
print('====================(2/15)==============================')
print("""
Title: The title of the target package. 
E.g. Full genome sequences for Rattus norvegicus (UCSC version rn4)
Give a short description of the package. Some package listings may truncate the title to 65 characters. It should use title case (that is, use capitals for the principal words: tools::toTitleCase can help you with this), not use any markup, not have any continuation lines, and not end in a period (unless part of …). Do not repeat the package name: it is often used prefixed by the name. Refer to other packages and external software in single quotes, and to book titles (and similar) in double quotes.
""")
print('==================================================')
Title = input("Please enter the Title name: ").strip()

# Prompt user for Description information
print('====================(3/15)==============================')
print("""
Give a comprehensive description of what the package does. 
One can use several (complete) sentences, but only one paragraph. 
It should be intelligible to all the intended readership (e.g. for a CRAN package to all CRAN users). 
It is good practice not to start with the package name, ‘This package’ or similar. 
As with the ‘Title’ field, double quotes should be used for quotations (including titles of books and articles), and single quotes for non-English usage, including names of other packages and external software. 
This field should also be used for explaining the package name if necessary. 
""")
print('==================================================')
Description = input("Please enter the Description: ").strip()

# Prompt user for Version information
print('====================(4/15)==============================')
print("""
gives the version of the package. 
This is a sequence of at least two (and usually three) non-negative integers separated by single ‘.’ or ‘-’ characters. 
The canonical form is as shown in the example, and a version such as ‘0.01’ or ‘0.01.0’ will be handled as if it were ‘0.1-0’. 
It is not a decimal number, so for example 0.9 < 0.75 since 9 < 75.
""")
print('==================================================')
Version = input("Please enter the Version: ").strip()

# Prompt user for organism information
print('====================(5/15)==============================')
print("""
The scientific name of the organism in the format Genus species (e.g. Triticum aestivum,
Homo sapiens) or Genus species subspecies (e.g. Homo sapiens neanderthalensis).
""")
print('==================================================')
organism = input("Please enter the organism: ").strip()

# Prompt user for common_name information
print('====================(6/15)==============================')
print("""
The common name of the organism (e.g. Rat or Human). For organisms that have more than one commmon name (e.g. Bovine or Cow for Bos taurus), choose one.
""")
print('==================================================')
common_name = input("Please enter the common_name: ").strip()

# Prompt user for genome information
print('====================(7/15)==============================')
print("""
The name of the genome. Typically the name of an NCBI assembly (e.g. GRCh38.p12, WBcel235, TAIR10.1, ARS-UCD1.2, etc...) or UCSC genome (e.g. hg38, bosTau9, galGal6, ce11, etc...). Should preferably match part 4 of the package name (field Package). 
""")
print('Accroding to your input, I suggest this filed set to：', package_name.split(".")[3])
print('==================================================')
genome = input("Please enter the common_name: ").strip()

# Prompt user for provider information
print('====================(8/15)==============================')
print("""
The provider of the sequence data files e.g. UCSC, NCBI, BDGP, FlyBase, etc... Should preferably match part 3 of the package name (field Package).
""")
print('Accroding to your input, I suggest this filed set to：', package_name.split(".")[2])
print('==================================================')
provider = input("Please enter the provider: ").strip()

# Prompt user for release_date information
print('====================(9/15)==============================')
print("""
When this assembly of the genome was released in MM. YYYY format. e.g.:Apr. 2011 
""")
print('==================================================')
release_date = input("Please enter the release_date: ").strip()

# Prompt user for source_url information
print('====================(10/15)==============================')
print("""
The permanent URL where the sequence data files used to forge the target package can
be found. If the target package is for an NCBI assembly, use the link to the NCBI landing page for the
assembly e.g. https://www.ncbi.nlm.nih.gov/assembly/GCF_003254395.2/
""")
print('==================================================')
source_url = input("Please enter the source_url: ").strip()

# Prompt user for organism_biocview information
print('====================(11/15)==============================')
print("""
The official biocViews term for this organism. This is generally the same as the organism field except that spaces should be replaced with underscores. The value of this field matters only if the target package is going to be added to a Bioconductor repository, because it will determine where the package will show up in the biocViews tree(https://bioconductor.org/packages/release/BiocViews.html#___Organism). Note that this is the only field in this category that won't get stored in the BSgenome object that will get wrapped in the target package.
""")
print('==================================================')
organism_biocview = input("Please enter the organism_biocview: ").strip()

# Prompt user for BSgenomeObjname information
print('====================(12/15)==============================')
print("""
Should match part 2 of the package name (see Package field above).
""")
print('Accroding to your input, I suggest this filed set to：', package_name.split(".")[1])
print('==================================================')
BSgenomeObjname = input("Please enter the BSgenomeObjname: ").strip()

# Prompt user for circ_seqs information
print('====================(13/15)==============================')
print("""
Not needed if your NCBI assembly or UCSC genome is registered in the GenomeInfoDb package. An R expression returning the names of the circular sequences (in a character vector). If the seqnames field is specified, then circ_seqs must be a subset of it. E.g. "chrM" for rn4 or c("chrM", "2micron") for the sacCer2 genome (Yeast) from UCSC. If the assembly or genome has no circular
sequence, set circ_seqs to character(0).
""")
print('==================================================')
circ_seqs = input("Please enter the circ_seqs: ").strip()

# Prompt user for seqs_srcdir information
print('====================(14/15)==============================')
print("""
 The absolute path to the folder containing the sequence data files
""")
print('==================================================')
seqs_srcdir = input("Please enter the seqs_srcdir: ").strip()

# Prompt user for seqfile_name information
print('====================(15/15)==============================')
print("""
Required if the sequence data files is a single twoBit file
""")
print('==================================================')
seqfile_name = input("Please enter the seqfile_name: ").strip()

# Write package name to file
# with open(package_name + '.seed', 'w') as f:
#     f.write("Package: ", package_name)
#     f.write(title)
#     f.write(Description)
#     f.write(Version)
#     f.write(organism)
#     f.write(common_name)
#     f.write(genome)
#     f.write(provider)
#     f.write(release_date)
#     f.write(source_url)
#     f.write(organism_biocview)
#     f.write(BSgenomeObjname)    
#     f.write(circ_seqs)
#     f.write(seqs_srcdir)    
#     f.write(seqfile_name)
# print(f"The package name has been written to {package_name}.seed")

print('Here is the seed file information:')
print('==================================================')
print("Package: ", package_name)
print("Title: ", Title)
print("Description: ", Description)
print("Version: ", Version)
print("organism: ", organism)
print("common_name: ", common_name)
print("genome: ", genome)
print("provider: ", provider)
print("release_date: ", release_date)
print("source_url: ", source_url)
print("organism_biocview: ", organism_biocview)
print("BSgenomeObjname: ", BSgenomeObjname)
print("circ_seqs: ", circ_seqs)
print("seqs_srcdir: ", seqs_srcdir)
print("seqfile_name: ", seqfile_name)

