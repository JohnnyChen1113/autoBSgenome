#!/usr/bin/env python

"""
Script Name: autoBSgenome
Author: Junhao Chen
Date: 2024-08-26
Version: 0.2.0
Description: A wrap for build a BSgenome
"""

import os
import datetime
import subprocess
import glob

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

import rich as rich
from rich import print
from rich.markdown import Markdown

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

####### prompt information zone #######
# Prompt user for package information
package_info = """
# (1/15) Package Information
**Package**: Name to give to the target package.

The convention used for the packages built by the Bioconductor project is to use a name made of 4 parts separated by a dot.

- **Part 1** is always BSgenome.
- **Part 2** is the abbreviated name of the organism (when the name of the organism is made of 2 words, we put together the first letter of the first word in upper case followed by the entire second word in lower case e.g. Rnorvegicus).
- **Part 3** is the name of the organisation who provided the genome (e.g. UCSC).
- **Part 4** is the release string or number used by this organisation to identify this version of the genome (e.g. rn4).
"""

# title information
title_info = """
# (2/15) Title: The title of the target package
**Example**: Full genome sequences for Rattus norvegicus (UCSC version rn4)
- Give a short description of the package. Some package listings may truncate the title to 65 characters.

- It should use title case (that is, use capitals for the principal words: tools::toTitleCase can help you with this), not use any markup, not have any continuation lines, and not end in a period (unless part of …).

- Do not repeat the package name: it is often used prefixed by the name.

- Refer to other packages and external software in single quotes, and to book titles (and similar) in double quotes.
"""

# discription
discription_info = """
# (3/15) Description

Give a comprehensive description of what the package does. (optional! You can just left it blank if you have no idea how to set it)

- One can use several (complete) sentences, but only one paragraph.
- It should be intelligible to all the intended readership (e.g. for a CRAN package to all CRAN users).
- It is good practice not to start with the package name, ‘This package’ or similar.
- As with the ‘Title’ field, double quotes should be used for quotations (including titles of books and articles), and single quotes for non-English usage, including names of other packages and external software.
- This field should also be used for explaining the package name if necessary.
"""

# Version information
version_info = """
# (4/15) Version information
gives the version of the package.
- This is a sequence of at least two (and usually three) non-negative integers separated by single ‘.’ or ‘-’ characters.
- The canonical form is as shown in the example, and a version such as **‘0.01’** or **‘0.01.0’** will be handled as if it were **‘0.1-0’**.
- It is not a decimal number, so for example 0.9 < 0.75 since 9 < 75.
"""

# organism information
organism_info = """
# (5/15) Organism information
The **scientific name** of the organism in the format Genus species (e.g. Triticum aestivum, Homo sapiens) or Genus species subspecies (e.g. Homo sapiens neanderthalensis).
"""

# common_name information
common_name_info = """
# (6/15) Common name information
The **common name** of the organism (e.g. Rat or Human). For organisms that have **more than one** commmon name (e.g. Bovine or Cow for Bos taurus), choose one.
"""

# genome information
genome_info = """
# (7/15) Genome information
The name of the genome. 
- Typically the name of an NCBI assembly (e.g. GRCh38.p12, WBcel235, TAIR10.1, ARS-UCD1.2, etc...) or UCSC genome (e.g. hg38, bosTau9, galGal6, ce11, etc...). 
- Should preferably match part 4 of the package name (field Package).

"""

# provider information
provider_info = """
# (8/15) Provider information
The provider of the sequence data files e.g. UCSC, NCBI, BDGP, FlyBase, etc... 
- Should preferably match part 3 of the package name (field Package).
"""

# release_date information
release_date_info = """
# (9/15) Release date information
When this assembly of the genome was released in MM. YYYY format. 
- e.g.:Apr. 2011
"""

# source_url information
source_url_info = """
# (10/15) Source URL information
== (optional! You can just left it blank if you have no idea how to set it) ==
The permanent URL where the sequence data files used to forge the target package can be found. 
- If the target package is for an NCBI assembly, use the link to the NCBI landing page for the assembly 
- e.g. https://www.ncbi.nlm.nih.gov/assembly/GCF_003254395.2/
"""

# organism_biocview information
organism_biocview_info = """
# (11/15) Organism biocview information
(optional! You can just left it blank if you have no idea how to set it)
The official biocViews term for this organism. 
- This is generally the same as the organism field except that spaces should be replaced with underscores. 
- The value of this field matters only if the target package is going to be added to a Bioconductor repository, 
because it will determine where the package will show up in the biocViews tree(https://bioconductor.org/packages/release/BiocViews.html#___Organism). 
- **Note that this is the only field in this category that won't get stored in the BSgenome object that will get wrapped in the target package.**
"""

# BSgenomeObjname information
BSgenomeObjname_info = """
# (12/15) BSgenomeObjname information
Should match part 2 of the package name (see Package field above).
"""

# circ_seqs information
circ_seqs_info = """
# (13/15) circ_seqs information
Not needed if your NCBI assembly or UCSC genome is registered in the GenomeInfoDb package. 
- An R expression returning the names of the circular sequences (in a character vector). 
- If the seqnames field is specified, then circ_seqs must be a subset of it. E.g. "chrM" for rn4 or c("chrM", "2micron") for the sacCer2 genome (Yeast) from UCSC. 
- If the assembly or genome has no circular sequence, set circ_seqs to == character(0) ==
"""

# seqs_srcdir information
seqs_srcdir_info = """
# (14/15) seqs_srcdir information
The absolute path to the folder containing the sequence data files.
"""

# seqfile_name information
seqfile_name_info = """
# (15/15) seqfile_name information
Required if the sequence data files is a single twoBit file. 
If you dot have a twoBit file, just input a fasta file name, I will automatic cover it to .2bit format for you!
"""

########################################

####### input zone #######
print(Markdown(package_info))
package_name = prompt("Please enter the package name: ").strip()

# Check if the package name is valid
valid_package = True
parts = package_name.split(".")
if len(parts) != 4 or parts[0] != "BSgenome":
    valid_package = False
    print("[bold red]Not valid name! Please start with 'BSgenome'.[/bold red]")
    exit("Exiting due to invalid package name.")

if not valid_package:
    print("[bold yellow]The package name is not valid.[/bold yellow]")
    exit("Exiting due to invalid package name.")
else:
    print("[bold green]The package name is valid.[/bold green]")

print(Markdown(title_info))
Title = prompt("Please enter the title: ").strip()

print(Markdown(discription_info))
Description = prompt("Please enter the Description: ").strip()

print(Markdown(version_info))
Version = prompt("Please enter the Version: ").strip()

print(Markdown(organism_info))
organism = prompt("Please enter the organism: ").strip()

print(Markdown(common_name_info))
common_name = prompt("Please enter the common_name: ").strip()

print(Markdown(genome_info))
print('Accroding to your input, I suggest this filed set to：', package_name.split(".")[3])
genome = prompt("Please enter the common_name: ").strip()

print(Markdown(provider_info))
print('Accroding to your input, I suggest this filed set to：', package_name.split(".")[2])
provider = prompt("Please enter the provider: ").strip()

print(Markdown(release_date_info))
print('Today is:', datetime.date.today().strftime("%m. %Y"))
release_date = prompt("Please enter the release_date: ").strip() 

print(Markdown(source_url_info))
source_url = prompt("Please enter the source_url: ").strip()

print(Markdown(organism_biocview_info))
organism_biocview = prompt("Please enter the organism_biocview: ").strip()

print(Markdown(BSgenomeObjname_info))
print('Accroding to your input, I suggest this filed set to：', package_name.split(".")[1])
BSgenomeObjname = prompt("Please enter the BSgenomeObjname: ").strip()

print(Markdown(circ_seqs_info))
circ_seqs = prompt("Please enter the circ_seqs: ").strip()

print(Markdown(seqs_srcdir_info))
print("Now you are in %s" % os.getcwd())
seqs_srcdir = prompt("Please enter the seqs_srcdir: ").strip()

print(Markdown(seqfile_name_info))
fasta_files = glob.glob("*.fasta")
fa_files = glob.glob("*.fa")
fna_files = glob.glob("*.fna")
fasta_files.extend(fa_files)
fasta_files.extend(fna_files)
print('All the fa / fasta file in current folder list here:',fasta_files)

seqfile_name = prompt("Please enter the seqfile_name: ").strip()
TowBit_name = seqfile_name.rsplit('.', 1)[0] + '.2bit' if seqfile_name.endswith(('.fa', '.fna', '.fasta', '.fas')) else seqfile_name

##########################

yes_no_completer = WordCompleter(['Y', 'N'], ignore_case=True)

def get_user_decision():
    while True:
        user_decision = prompt("Do you want to print the content? (Y/N): ", completer=yes_no_completer).strip().upper()
        if user_decision in ['Y', 'N']:
            return user_decision
        else:
            print("Invalid input. Please enter 'Y' or 'N'.")

user_print_decision = get_user_decision()
if user_print_decision == 'Y':
    print()
    print('Here is the seed file information:')
    print('==================================================')
    print("Package: ", package_name)
    print("Title: ", Title)
    print("Description: ", Description)
    print("Version: ", Version)
    print("Organism: ", organism)
    print("Common name: ", common_name)
    print("Genome: ", genome)
    print("Provider: ", provider)
    print("Release date: ", release_date)
    print("Source URL: ", source_url)
    print("Organism BiocView: ", organism_biocview)
    print("BSgenome Objname: ", BSgenomeObjname)
    print("Circular sequences: ", circ_seqs)
    print("Sequences source directory: ", seqs_srcdir)
    print("Two-bit file name: ", TowBit_name)
elif user_print_decision == 'N':
    print("Skipping content printing.")


filename=package_name + '.seed'
with open(filename,'wt') as seed_file:
    seed_file.write(f"Package: {package_name}\n")
    seed_file.write(f"Title: {Title}\n")
    seed_file.write(f"Description: {Description}\n")
    seed_file.write(f"Version: {Version}\n")
    seed_file.write(f"organism: {organism}\n")
    seed_file.write(f"common_name: {common_name}\n")
    seed_file.write(f"genome: {genome}\n")
    seed_file.write(f"provider: {provider}\n")
    seed_file.write(f"release_date: {release_date}\n")
    seed_file.write(f"source_url: {source_url}\n")
    seed_file.write(f"organism_biocview: {organism_biocview}\n")
    seed_file.write(f"BSgenomeObjname: {BSgenomeObjname}\n")
    seed_file.write(f"circ_seqs: {circ_seqs}\n")
    seed_file.write(f"seqs_srcdir: {seqs_srcdir}\n")
    seed_file.write(f"seqfile_name: {TowBit_name}\n")
print()
print('You can build the package using this steps in an R script:')
print('==================================================')
print('library(BSgenome)')
print('forgeBSgenomeDataPkg("%s/%s")' % (seqs_srcdir,filename))
print('system("R CMD build %s")' % package_name)

generate_2bit = f"faToTwoBit  {seqfile_name} {TowBit_name}"
subprocess.run(generate_2bit, shell=True)

file_name = input("Please enter the script name or press enter to use 'build.R': ")
if not file_name.strip():
    file_name = "build.R"
with open(file_name, 'wt') as seed_file:
    seed_file.write("library(BSgenome)\n")
    seed_file.write(f"forgeBSgenomeDataPkg('{filename}')\n")
    seed_file.write(f"dir.create('./{package_name}/inst/extdata/', recursive = TRUE)\n") # Create folder
    seed_file.write(f"file.copy('./{TowBit_name}', './{package_name}/inst/extdata/single_sequences.2bit')\n") # Copy file
    seed_file.write(f"system('R CMD build {package_name}')\n")
    seed_file.write(f"system('R CMD INSTALL {package_name}')\n")    


build_package = f"Rscript {file_name}"
subprocess.run(build_package, shell=True)

