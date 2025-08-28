#!/usr/bin/env python

"""
Script Name: autoBSgenome
Author: Junhao Chen
Date: 2024-08-26
Updated date: 2025-08-27
Version: 0.6.1
Description: A wrap for build a BSgenome
"""

import os
import datetime
import subprocess
import glob
import shutil
from prompt_toolkit import prompt
from rich import print
from rich.markdown import Markdown

from prompts import PROMPT_TEXTS

def check_and_install_dependencies():
    """Checks for faToTwoBit and installs it if necessary."""
    if shutil.which("faToTwoBit"):
        print('faToTwoBit is already installed.')
        return "faToTwoBit"

    answer = prompt('faToTwoBit is not found. Do you want to download and install it? (yes/no) ').strip().lower()
    if answer != 'yes':
        print('faToTwoBit is not installed. Exiting.')
        exit()

    print('Downloading faToTwoBit...')
    try:
        subprocess.run(['curl', '-O', 'http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit'], check=True)
        subprocess.run(['chmod', '+x', 'faToTwoBit'], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[bold red]Failed to download or set permissions for faToTwoBit: {e}[/bold red]")
        exit()

    install_path = ""
    if os.access('/usr/local/bin', os.W_OK):
        try:
            shutil.move('faToTwoBit', '/usr/local/bin/')
            install_path = '/usr/local/bin/faToTwoBit'
            print(f'faToTwoBit has been installed successfully in {install_path}.')
        except Exception as e:
            print(f'[bold red]Failed to move faToTwoBit to /usr/local/bin: {e}[/bold red]')
    
    if not install_path:
        try:
            shutil.move('faToTwoBit', './faToTwoBit')
            install_path = './faToTwoBit'
            print('faToTwoBit has been installed successfully in the current directory.')
            print('Please run it from the current directory or add this directory to your PATH.')
        except Exception as e:
            print(f'[bold red]Failed to move faToTwoBit to the current directory: {e}[/bold red]')
            exit()
            
    return install_path

def get_user_input():
    """Gathers all necessary metadata from the user via prompts."""
    
    metadata = {}

    # --- Package Name ---
    print(Markdown(PROMPT_TEXTS["package"]))
    package_name = prompt("Please enter the package name: ").strip()
    parts = package_name.split(".")
    if len(parts) != 4 or parts[0] != "BSgenome":
        print("[bold red]Not valid name! Please start with 'BSgenome.' and have 4 parts.[/bold red]")
        exit("Exiting due to invalid package name.")
    print("[bold green]The package name is valid.[/bold green]")
    metadata['package_name'] = package_name

    # --- Other Metadata ---
    print(Markdown(PROMPT_TEXTS["title"]))
    metadata['title'] = prompt("Please enter the title: ").strip()

    print(Markdown(PROMPT_TEXTS["description"]))
    metadata['description'] = prompt("Please enter the Description: ").strip()

    print(Markdown(PROMPT_TEXTS["version"]))
    metadata['version'] = prompt("Please enter the Version: ").strip()

    print(Markdown(PROMPT_TEXTS["organism"]))
    metadata['organism'] = prompt("Please enter the organism: ").strip()

    print(Markdown(PROMPT_TEXTS["common_name"]))
    metadata['common_name'] = prompt("Please enter the common_name: ").strip()

    print(Markdown(PROMPT_TEXTS["genome"]))
    print(f"According to your input, I suggest this field set to: {parts[3]}")
    metadata['genome'] = prompt("Please enter the genome: ", default=parts[3]).strip()

    print(Markdown(PROMPT_TEXTS["provider"]))
    print(f"According to your input, I suggest this field set to: {parts[2]}")
    metadata['provider'] = prompt("Please enter the provider: ", default=parts[2]).strip()

    print(Markdown(PROMPT_TEXTS["release_date"]))
    today_str = datetime.date.today().strftime("%b. %Y")
    print(f"Today is: {today_str}")
    metadata['release_date'] = prompt("Please enter the release_date: ", default=today_str).strip()

    print(Markdown(PROMPT_TEXTS["source_url"]))
    metadata['source_url'] = prompt("Please enter the source_url: ").strip()

    print(Markdown(PROMPT_TEXTS["organism_biocview"]))
    metadata['organism_biocview'] = prompt("Please enter the organism_biocview: ").strip()

    print(Markdown(PROMPT_TEXTS["BSgenomeObjname"]))
    print(f"According to your input, I suggest this field set to: {parts[1]}")
    metadata['BSgenomeObjname'] = prompt("Please enter the BSgenomeObjname: ", default=parts[1]).strip()

    print(Markdown(PROMPT_TEXTS["circ_seqs"]))
    metadata['circ_seqs'] = prompt("Please enter the circ_seqs: ").strip()

    print(Markdown(PROMPT_TEXTS["seqs_srcdir"]))
    print(f"Now you are in {os.getcwd()}")
    metadata['seqs_srcdir'] = prompt("Please enter the seqs_srcdir: ", default=os.getcwd()).strip()

    print(Markdown(PROMPT_TEXTS["seqfile_name"]))
    fasta_files = glob.glob("*.fasta") + glob.glob("*.fa") + glob.glob("*.fas") + glob.glob("*.fna")
    print('All the fa/fasta files in current folder list here:', fasta_files)
    metadata['seqfile_name'] = prompt("Please enter the seqfile_name: ").strip()
    
    metadata['twobit_name'] = metadata['seqfile_name'].rsplit('.', 1)[0] + '.2bit' if metadata['seqfile_name'].endswith(('.fa', '.fna', '.fasta', '.fas')) else metadata['seqfile_name']

    return metadata

def create_seed_file(metadata):
    """Creates the .seed file from the provided metadata."""
    seed_filename = metadata['package_name'] + '.seed'
    print(f"\n[bold green]Generating seed file: {seed_filename}[/bold green]")
    
    content = f"""
Package: {metadata['package_name']}
Title: {metadata['title']}
Description: {metadata['description']}
Version: {metadata['version']}
organism: {metadata['organism']}
common_name: {metadata['common_name']}
genome: {metadata['genome']}
provider: {metadata['provider']}
release_date: {metadata['release_date']}
source_url: {metadata['source_url']}
organism_biocview: {metadata['organism_biocview']}
BSgenomeObjname: {metadata['BSgenomeObjname']}
circ_seqs: {metadata['circ_seqs']}
seqs_srcdir: {metadata['seqs_srcdir']}
seqfile_name: {metadata['twobit_name']}
"""
    with open(seed_filename, 'w') as f:
        f.write(content.strip())
    
    print('--- Seed File Content ---')
    print(content.strip())
    print('-------------------------')
    return seed_filename

def run_faToTwoBit(faToTwoBit_path, metadata):
    """Converts FASTA to 2bit format."""
    print(f"\n[bold green]Converting {metadata['seqfile_name']} to {metadata['twobit_name']}...[/bold green]")
    command = [faToTwoBit_path, metadata['seqfile_name'], metadata['twobit_name']]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[bold red]Error converting to 2bit format:[/bold red]")
        print(result.stderr)
    else:
        print('[bold green]Conversion successful.[/bold green]')

def create_and_run_build_script(metadata, seed_filename):
    """Creates the build.R script and optionally runs it."""
    build_script_name = prompt("Press ENTER to use default script name 'build.R', or enter a new name: ").strip()
    if not build_script_name:
        build_script_name = "build.R"

    package_name = metadata['package_name']
    twobit_name = metadata['twobit_name']

    if os.path.exists(package_name):
        shutil.rmtree(package_name)

    r_script_content = f"""
suppressPackageStartupMessages(library(BSgenome))
tryCatch({{
  if (dir.exists('{package_name}')) {{ unlink('{package_name}', recursive = TRUE) }}
  forgeBSgenomeDataPkg('{seed_filename}')
}}, error = function(e) {{
  message('Error occurred during forgeBSgenomeDataPkg: ', e$message)
  # Fallback to manual creation if forging fails at certain steps
  dir.create('./{package_name}/inst/extdata/', recursive = TRUE, showWarnings = FALSE)
  file.copy('./{twobit_name}', './{package_name}/inst/extdata/single_sequences.2bit')
}})
system('R CMD build {package_name}')
system('R CMD INSTALL {package_name}')
"""
    with open(build_script_name, 'w') as f:
        f.write(r_script_content.strip())
    
    print(f"\n[bold green]Generated build script: {build_script_name}[/bold green]")
    print('You can build the package using this R command:')
    print(f"Rscript {build_script_name}")

    install_answer = prompt("Do you want to install the package now? (yes/no): ").strip().lower()
    if install_answer == 'yes':
        print('[bold green]Running build and installation...[/bold green]')
        subprocess.run(['Rscript', build_script_name])
    else:
        print("Skipping package installation.")

def main():
    """Main function to orchestrate the BSgenome package creation."""
    faToTwoBit_path = check_and_install_dependencies()
    metadata = get_user_input()
    seed_filename = create_seed_file(metadata)
    run_faToTwoBit(faToTwoBit_path, metadata)
    create_and_run_build_script(metadata, seed_filename)
    print("\n[bold green]Process completed.[/bold green]")

if __name__ == "__main__":
    main()
