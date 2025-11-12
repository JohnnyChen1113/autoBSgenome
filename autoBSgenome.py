#!/usr/bin/env python

"""
Script Name: autoBSgenome
Author: Junhao Chen
Date: 2024-08-26
Updated date: 2025-08-27
Version: 0.8.0
Description: A wrap for build a BSgenome
"""

import os
import sys
import datetime
import subprocess
import glob
import shutil
import argparse
from prompt_toolkit import prompt
from rich import print
from rich.markdown import Markdown
from rich.table import Table
from rich.console import Console

from prompts import PROMPT_TEXTS

console = Console()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog='autoBSgenome',
        description='Interactive tool for building R BSgenome packages',
        epilog='For more information, visit: https://github.com/JohnnyChen1113/autoBSgenome',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 0.8.0'
    )

    parser.add_argument(
        '--config',
        metavar='FILE',
        help='Load configuration from a JSON file (future feature)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration without building the package'
    )

    parser.add_argument(
        '--skip-deps-check',
        action='store_true',
        help='Skip dependency checks (use with caution)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    return parser.parse_args()

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
    console.print('[yellow]⚠ faToTwoBit tool is not found on your system.[/yellow]')
    console.print('This tool is required to convert FASTA files to 2bit format.')
    answer = prompt('Would you like to download and install it now? (yes/no) ').strip().lower()
    if answer != 'yes':
        console.print('[bold red]✗ Cannot proceed without faToTwoBit. Exiting.[/bold red]')
        console.print('[dim]You can manually install it from: http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit[/dim]')
        sys.exit(1)

    console.print('[cyan]↓ Downloading faToTwoBit...[/cyan]')
    try:
        # Download to the current directory
        subprocess.run(['curl', '-O', 'http://hgdownload.soe.ucsc.edu/admin/exe/linux.x86_64/faToTwoBit'], check=True)
        subprocess.run(['chmod', '+x', 'faToTwoBit'], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]✗ Download failed: {e}[/bold red]")
        console.print('[yellow]Please check your internet connection and try again.[/yellow]')
        sys.exit(1)
    except FileNotFoundError:
        console.print("[bold red]✗ 'curl' command not found.[/bold red]")
        console.print('[yellow]Please install curl or manually download faToTwoBit.[/yellow]')
        sys.exit(1)

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
    console.print("[bold cyan]Checking R dependencies...[/bold cyan]")

    # First check if R is installed
    try:
        subprocess.run(['Rscript', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print("[bold red]✗ R is not installed or not in PATH.[/bold red]")
        console.print("[yellow]Please install R (version 4.2.0 or higher) and try again.[/yellow]")
        console.print("[dim]Visit: https://www.r-project.org/[/dim]")
        sys.exit(1)

    # Check if BiocManager is installed
    console.print("[dim]Checking for BiocManager...[/dim]")
    biocmanager_check = """
    if (!requireNamespace("BiocManager", quietly = TRUE)) {
        cat("missing")
    } else {
        cat("installed")
    }
    """

    try:
        result = subprocess.run(['Rscript', '-e', biocmanager_check],
                              capture_output=True, text=True, check=True)
        biocmanager_status = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]✗ Error checking BiocManager: {e}[/bold red]")
        sys.exit(1)

    # Install BiocManager if missing
    if biocmanager_status == "missing":
        console.print("[yellow]⚠ BiocManager is not installed.[/yellow]")
        console.print("[dim]BiocManager is required to install Bioconductor packages.[/dim]")

        answer = prompt("Would you like to install BiocManager now? (yes/no) ").strip().lower()
        if answer != 'yes':
            console.print("[bold red]✗ Cannot proceed without BiocManager. Exiting.[/bold red]")
            console.print("[dim]Manual installation in R: install.packages('BiocManager')[/dim]")
            sys.exit(1)

        console.print("[cyan]Installing BiocManager...[/cyan]")
        biocmanager_install = """
        options(repos = c(CRAN = "https://cloud.r-project.org"))
        install.packages("BiocManager", quiet = TRUE)
        """

        install_result = subprocess.run(['Rscript', '-e', biocmanager_install],
                                       capture_output=True, text=True)
        if install_result.returncode != 0:
            console.print("[bold red]✗ Failed to install BiocManager.[/bold red]")
            console.print(f"[dim]Error: {install_result.stderr}[/dim]")
            console.print("[yellow]Please install manually in R:[/yellow]")
            console.print("[dim]  install.packages('BiocManager')[/dim]")
            sys.exit(1)

        console.print("[bold green]✓ BiocManager installed successfully.[/bold green]")
    else:
        console.print("[dim]✓ BiocManager is already installed.[/dim]")

    # Command to find missing packages
    r_check_command = f"""
    packages <- c('{required_packages[0]}', '{required_packages[1]}');
    missing_packages <- packages[!sapply(packages, function(p) requireNamespace(p, quietly = TRUE))];
    cat(paste(missing_packages, collapse=','))
    """

    try:
        result = subprocess.run(['Rscript', '-e', r_check_command], capture_output=True, text=True, check=True)
        missing_packages_str = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]✗ Error checking R packages: {e}[/bold red]")
        sys.exit(1)

    if not missing_packages_str:
        console.print("[bold green]✓ All required R packages are installed.[/bold green]")
        return

    missing_packages = missing_packages_str.split(',')
    console.print(f"[yellow]⚠ Missing R packages: {', '.join(missing_packages)}[/yellow]")
    console.print("[dim]These packages are required from Bioconductor.[/dim]")

    answer = prompt("Would you like to install them now? (yes/no) ").strip().lower()
    if answer != 'yes':
        console.print("[bold red]✗ Cannot proceed without required R packages. Exiting.[/bold red]")
        pkg_list = "', '".join(missing_packages)
        console.print(f"[dim]Manual installation: BiocManager::install(c('{pkg_list}'))[/dim]")
        sys.exit(1)

    console.print("[bold cyan]Installing R packages from Bioconductor...[/bold cyan]")
    console.print("[dim]This may take a few minutes...[/dim]")

    # Command to install packages
    packages_to_install_str = 'c(' + ','.join([f'\"{p}\"' for p in missing_packages]) + ')'
    r_install_command = f"""
    BiocManager::install({packages_to_install_str}, update=FALSE, ask=FALSE)
    """

    install_process = subprocess.run(['Rscript', '-e', r_install_command],
                                    capture_output=True, text=True)
    if install_process.returncode != 0:
        console.print("[bold red]✗ Failed to install R packages.[/bold red]")
        console.print(f"[dim]Error output: {install_process.stderr[:500]}[/dim]")
        console.print("[yellow]Please try installing manually in R:[/yellow]")
        pkg_list = "', '".join(missing_packages)
        console.print(f"[dim]  BiocManager::install(c('{pkg_list}'))[/dim]")
        sys.exit(1)

    console.print("[bold green]✓ R packages installed successfully.[/bold green]")

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

def preview_configuration(metadata):
    """Display configuration summary and ask for confirmation."""
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]Configuration Summary[/bold cyan]")
    console.print("=" * 60 + "\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="green")

    # Display metadata in a nice table
    field_labels = {
        'package_name': 'Package Name',
        'title': 'Title',
        'description': 'Description',
        'version': 'Version',
        'organism': 'Organism',
        'common_name': 'Common Name',
        'genome': 'Genome',
        'provider': 'Provider',
        'release_date': 'Release Date',
        'source_url': 'Source URL',
        'organism_biocview': 'Organism BiocView',
        'BSgenomeObjname': 'BSgenome Object Name',
        'circ_seqs': 'Circular Sequences',
        'seqs_srcdir': 'Sequences Source Dir',
        'seqfile_name': 'Sequence File Name',
        'twobit_name': '2bit File Name'
    }

    for key, label in field_labels.items():
        value = metadata.get(key, '')
        # Truncate long values
        if len(str(value)) > 60:
            value = str(value)[:57] + '...'
        table.add_row(label, str(value))

    console.print(table)
    console.print("\n" + "=" * 60 + "\n")

    # Ask for confirmation
    while True:
        choice = prompt(
            "Please review the configuration above. Choose an option:\n"
            "  [c] Continue with this configuration\n"
            "  [e] Edit a field\n"
            "  [q] Quit\n"
            "Your choice (c/e/q): "
        ).strip().lower()

        if choice == 'c':
            console.print("[bold green]✓ Configuration confirmed. Proceeding...[/bold green]\n")
            return True
        elif choice == 'e':
            console.print("\n[yellow]Edit functionality will be available in a future version.[/yellow]")
            console.print("[yellow]For now, please restart the script if you need to change values.[/yellow]\n")
            continue
        elif choice == 'q':
            console.print("[yellow]Configuration cancelled by user. Exiting.[/yellow]")
            return False
        else:
            console.print("[red]Invalid choice. Please enter 'c', 'e', or 'q'.[/red]")

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
    # Parse command line arguments
    args = parse_arguments()

    # Display welcome message
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   autoBSgenome - BSgenome Package Builder[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")

    # Check dependencies unless skipped
    if not args.skip_deps_check:
        faToTwoBit_path = check_and_install_dependencies()
        check_r_dependencies()
    else:
        console.print("[yellow]⚠ Skipping dependency checks (--skip-deps-check)[/yellow]")
        faToTwoBit_path = shutil.which("faToTwoBit") or './faToTwoBit'

    # Get user input
    metadata = get_user_input()

    # Preview configuration and get confirmation
    if not preview_configuration(metadata):
        console.print("[yellow]Exiting without building package.[/yellow]")
        sys.exit(0)

    # Handle dry-run mode
    if args.dry_run:
        console.print("\n[bold yellow]DRY RUN MODE - No files will be created[/bold yellow]")
        console.print("[green]✓ Configuration is valid[/green]")
        console.print("[dim]Would create seed file: {}.seed[/dim]".format(metadata['package_name']))
        console.print("[dim]Would convert: {} -> {}[/dim]".format(
            metadata['seqfile_name'], metadata['twobit_name']))
        console.print("\n[bold green]✓ Dry run completed successfully.[/bold green]")
        return

    # Create seed file
    seed_filename = create_seed_file(metadata)

    # Convert FASTA to 2bit
    try:
        run_faToTwoBit(faToTwoBit_path, metadata)
    except Exception as e:
        console.print(f"[bold red]✗ Error during FASTA to 2bit conversion: {e}[/bold red]")
        console.print("[yellow]Please check your input file and try again.[/yellow]")
        sys.exit(1)

    # Build and install package
    try:
        create_and_run_build_script(metadata, seed_filename)
    except Exception as e:
        console.print(f"[bold red]✗ Error during package build: {e}[/bold red]")
        sys.exit(1)

    console.print("\n[bold green]═══════════════════════════════════════[/bold green]")
    console.print("[bold green]✓ Process completed successfully![/bold green]")
    console.print("[bold green]═══════════════════════════════════════[/bold green]\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user. Exiting...[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected error: {e}[/bold red]")
        if '--verbose' in sys.argv:
            import traceback
            console.print("\n[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)
