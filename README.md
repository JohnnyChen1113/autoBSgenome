# autoBSgenome
A python warp of BSgenome. Build BSgenome like filling in a questionnaire!


# Installation

This script requires the installation of several packages and libraries to function correctly. You can install the necessary packages using either `conda` or `pip`. Ensure that Python is already installed on your system before proceeding.

## Dependencies

The script relies on the following Python libraries:
- `prompt_toolkit`
- `rich`
- Standard libraries: `os`, `datetime`, `subprocess`, `glob`

And this R package:
- `BSgenome`

You can install these using the following commands:
### Using pip
You can install the dependencies with pip
```
python -m pip install rich prompt_toolkit
```

### Using conda
For those who prefer using `conda`, you can install the packages using:
```
conda install -c conda-forge prompt_toolkit rich r-base bioconductor-bsgenome
```
If some of the required libraries are not available directly via conda, they might already be included in your Python installation as they are part of the Python Standard Library (os, datetime, subprocess, glob).

After installing the required packages, you can clone this repository to your local machine to get started. Use the following command to clone the repository:

```
git clone https://github.com/JohnnyChen1113/autoBSgenome.git
```
It will generate the `build.R` file for you!
# Alternative to BSgenomeForge
You also can try [BSgenomeForge](https://github.com/Bioconductor/BSgenomeForge), but it have some bug:
1. It cannot deal with ambiguous nucleotides in sequence (like Y means C or T, M means A or C, FYI: [IUPAC Codes](https://www.bioinformatics.org/sms/iupac.html))
2. It will verify the genome information with NCBI, but the information it gets is always the latest version, not the input version you used.

In these cases, you can try autoBSgenome :)

