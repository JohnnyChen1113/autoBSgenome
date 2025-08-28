#!/usr/bin/env python

"""
Script Name: autoBSgenome
Author: Junhao Chen
Date: 2024-08-26
Updated date: 2025-08-27
Version: 0.7.0
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
    # 1. Check if it's in the PATH
    faToTwoBit_path = shutil.which("faToTwoBit")
    if faToTwoBit_path:
        print(f'faToTwoBit is already installed at: {faToTwoBit_path}')
        return faToTwoBit_path

    # 2. Check if it's in the current directory
    if os.path.exists('./faToTwoBit'):
        print('faToTwoBit found in the current directory.')
        # Make sure it's executable
        subprocess.run(['chmod', '+x', './faToTwoBit'], check=True)
        return './faToTwoBit'

    # 3. If not found, ask to download
    answer = prompt('faToTwoBit is not found. Do you want to download and install it? (yes/no) ').strip().lower()
    if answer != 'yes':
        print('faToTwoBit is not installed. Exiting.')
        exit()

    print('Downloading faToTwoBit...')
    try:
        # Download to the current directory
        subprocess.run(['curl', '-O', 'http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit'], check=True)
        subprocess.run(['chmod', '+x', 'faToTwoBit'], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[bold red]Failed to download or set permissions for faToTwoBit: {e}[/bold red]")
        exit()

    # Try to move to a bin directory, but fall back to current dir
    install_path = ""
    if os.access('/usr/local/bin', os.W_OK):
        try:
            shutil.move('faToTwoBit', '/usr/local/bin/')
            install_path = '/usr/local/bin/faToTwoBit'
            print(f'faToTwoBit has been installed successfully in {install_path}.')
            return install_path
        except Exception as e:
            print(f'[bold red]Failed to move faToTwoBit to /usr/local/bin: {e}[/bold red]')
            print('[yellow]Using faToTwoBit from the current directory instead.[/yellow]')
    
    # If move failed or was not attempted, the file is in the current directory
    print('faToTwoBit is available in the current directory.')
    return './faToTwoBit'

def check_r_dependencies():
    """Checks for required R packages and prompts for installation if missing."""
    required_packages = ['BSgenome', 'BSgenomeForge']
    print("[bold green]Checking for required R packages...[/bold green]")
    
    # Command to find missing packages
    r_check_command = f"""
    packages <- c('{required_packages[0]}', '{required_packages[1]}');
    missing_packages <- packages[!sapply(packages, function(p) requireNamespace(p, quietly = TRUE))];
    cat(paste(missing_packages, collapse=','))
    """
    
    result = subprocess.run(['Rscript', '-e', r_check_command], capture_output=True, text=True)
    missing_packages_str = result.stdout.strip()
    
    if not missing_packages_str:
        print("All required R packages are already installed.")
        return

    missing_packages = missing_packages_str.split(',')
    print(f"[yellow]The following R packages are missing: {', '.join(missing_packages)}[/yellow]")
    
    answer = prompt("Do you want to install them now? (yes/no) ").strip().lower()
    if answer != 'yes':
        print("[bold red]Missing R packages are required to proceed. Exiting.[/bold red]")
        exit()
        
    print("[bold green]Installing missing R packages...[/bold green]")
    # Command to install packages
    packages_to_install_str = 'c(' + ','.join([f'\"{p}\"' for p in missing_packages]) + ')'
    r_install_command = f"""
    if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager");
    BiocManager::install({packages_to_install_str}, update=FALSE, ask=FALSE);
    """
    
    install_process = subprocess.run(['Rscript', '-e', r_install_command])
    if install_process.returncode != 0:
        print("[bold red]Failed to install R packages. Please install them manually and try again.[/bold red]")
        exit()
    
    print("[bold green]R packages installed successfully.[/bold green]")

def get_user_input():
    """Gathers all necessary metadata from the user via prompts in a wizard-like fashion."""
    
    print(Markdown("\n---\n*Entering interactive metadata entry mode. At any prompt, type `back` to return to the previous question.*---\n"))
    
    metadata = {}
    
    steps = [
        {
            'key': 'package_name',
            'prompt_text_key': "package",
            'display_text': "Please enter the package name: ",
            'validate': lambda val, data: len(val.split(".")) == 4 and val.split(".")[0] == "BSgenome",
            'on_error': lambda val, data: print("[bold red]Not valid name! Please start with 'BSgenome.' and have 4 parts.[/bold red]"),
            'on_success': lambda val, data: print("[bold green]The package name is valid.[/bold green]")
        },
        {'key': 'title', 'prompt_text_key': "title", 'display_text': "Please enter the title: "},
        {'key': 'description', 'prompt_text_key': "description", 'display_text': "Please enter the Description: "},
        {'key': 'version', 'prompt_text_key': "version", 'display_text': "Please enter the Version: "},
        {'key': 'organism', 'prompt_text_key': "organism", 'display_text': "Please enter the organism: "},
        {'key': 'common_name', 'prompt_text_key': "common_name", 'display_text': "Please enter the common_name: "},
        {
            'key': 'genome',
            'prompt_text_key': "genome",
            'display_text': "Please enter the genome: ",
            'get_default': lambda data: data.get('package_name', '').split('.')[3] if data.get('package_name') and len(data.get('package_name').split('.')) == 4 else ''
        },
        {
            'key': 'provider',
            'prompt_text_key': "provider",
            'display_text': "Please enter the provider: ",
            'get_default': lambda data: data.get('package_name', '').split('.')[2] if data.get('package_name') and len(data.get('package_name').split('.')) == 4 else ''
        },
        {
            'key': 'release_date',
            'prompt_text_key': "release_date",
            'display_text': "Please enter the release_date: ",
            'get_default': lambda data: datetime.date.today().strftime("%b. %Y")
        },
        {'key': 'source_url', 'prompt_text_key': "source_url", 'display_text': "Please enter the source_url: "},
        {'key': 'organism_biocview', 'prompt_text_key': "organism_biocview", 'display_text': "Please enter the organism_biocview: "},
        {
            'key': 'BSgenomeObjname',
            'prompt_text_key': "BSgenomeObjname",
            'display_text': "Please enter the BSgenomeObjname: ",
            'get_default': lambda data: data.get('package_name', '').split('.')[1] if data.get('package_name') and len(data.get('package_name').split('.')) == 4 else ''
        },
        {'key': 'circ_seqs', 'prompt_text_key': "circ_seqs", 'display_text': "Please enter the circ_seqs: "},
        {
            'key': 'seqs_srcdir',
            'prompt_text_key': "seqs_srcdir",
            'display_text': "Please enter the seqs_srcdir: ",
            'pre_prompt_action': lambda data: print(f"Now you are in {os.getcwd()}"),
            'get_default': lambda data: os.getcwd()
        },
        {
            'key': 'seqfile_name',
            'prompt_text_key': "seqfile_name",
            'display_text': "Please enter the seqfile_name: ",
            'pre_prompt_action': lambda data: print('All the fa/fasta files in current folder list here:', glob.glob("*.fasta") + glob.glob("*.fa") + glob.glob("*.fas") + glob.glob("*.fna"))
        },
    ]

    i = 0
    while i < len(steps):
        step = steps[i]
        
        print(Markdown(PROMPT_TEXTS[step['prompt_text_key']]))

        if 'pre_prompt_action' in step:
            step['pre_prompt_action'](metadata)

        default_value = metadata.get(step['key'], '')
        if 'get_default' in step:
            suggested_default = step['get_default'](metadata)
            if suggested_default:
                print(f"Suggested value: [cyan]{suggested_default}[/cyan]")
                default_value = suggested_default
        
        user_input = prompt(step['display_text'], default=default_value).strip()

        if user_input.lower() == 'back':
            if i > 0:
                i -= 1
            else:
                print("[yellow]Cannot go back further.[/yellow]")
            print(Markdown("---"))
            continue

        if 'validate' in step and not step['validate'](user_input, metadata):
            if 'on_error' in step:
                step['on_error'](user_input, metadata)
            continue
        
        if 'on_success' in step:
            step['on_success'](user_input, metadata)

        metadata[step['key']] = user_input
        
        i += 1
        print(Markdown("---"))

    seqfile = metadata.get('seqfile_name', '')
    if seqfile.endswith(('.fa', '.fna', '.fasta', '.fas')):
        metadata['twobit_name'] = seqfile.rsplit('.', 1)[0] + '.2bit'
    else:
        metadata['twobit_name'] = seqfile

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
        f.write(content.strip() + '\n')
    
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
    check_r_dependencies()
    metadata = get_user_input()
    seed_filename = create_seed_file(metadata)
    run_faToTwoBit(faToTwoBit_path, metadata)
    create_and_run_build_script(metadata, seed_filename)
    print("\n[bold green]Process completed.[/bold green]")

if __name__ == "__main__":
    main()
