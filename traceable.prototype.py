#!/usr/bin/env python

import os
import datetime
import subprocess
import glob
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
import rich
from rich import print
from rich.markdown import Markdown

# Check if essential tools are installed
if os.system('which faToTwoBit >/dev/null 2>&1') != 0:
    answer = input('faToTwoBit is not found. Do you want to download and install it? (yes/no) ').strip().lower()
    if answer == 'yes':
        os.system('curl -O http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit')
        os.system('chmod +x faToTwoBit')
        os.system('sudo mv faToTwoBit /usr/local/bin/')
        print('faToTwoBit has been installed successfully.')
    else:
        print('Installation skipped. faToTwoBit is required to continue.')
        exit()

# Helper functions
def get_input(title, default=''):
    print(Markdown(title))
    return prompt("Please enter your choice: ").strip() or default

def validate_input(input_dict, keys):
    while True:
        for key in keys:
            print(f"{key}: {input_dict[key]}")
        if prompt("Are these values correct? (Y/N): ").strip().lower() == 'y':
            break
        key_to_edit = prompt("Which value would you like to edit? ").strip()
        if key_to_edit in input_dict:
            input_dict[key_to_edit] = get_input(f"# {key_to_edit}")

# Data collection
questions = {
    "package_name": "# (1/15) Package Information\n**Package**: Name to give to the target package.",
    "title": "# (2/15) Title: The title of the target package",
    "description": "# (3/15) Description\nGive a comprehensive description of what the package does.",
    "version": "# (4/15) Version information",
    "organism": "# (5/15) Organism information",
    "common_name": "# (6/15) Common name information",
    "genome": "# (7/15) Genome information",
    "provider": "# (8/15) Provider information",
    "release_date": "# (9/15) Release date information",
    "source_url": "# (10/15) Source URL information",
    "organism_biocview": "# (11/15) Organism biocview information",
    "BSgenomeObjname": "# (12/15) BSgenomeObjname information",
    "circ_seqs": "# (13/15) circ_seqs information",
    "seqs_srcdir": "# (14/15) seqs_srcdir information",
    "seqfile_name": "# (15/15) seqfile_name information"
}

answers = {}
for key, value in questions.items():
    answers[key] = get_input(value)

validate_input(answers, questions.keys())

# Generate the seed file
filename = answers['package_name'] + '.seed'
with open(filename, 'wt') as seed_file:
    for key, value in answers.items():
        seed_file.write(f"{key}: {value}\n")

print(f"\nYou can build the package using this command:\nlibrary(BSgenome)\nforgeBSgenomeDataPkg('{answers['seqs_srcdir']}/{filename}')")

