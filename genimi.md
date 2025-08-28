# Proposal for Refactoring autoBSgenome.py

## 1. Problem Statement

The current `autoBSgenome.py` script operates as a rigid, linear process. The user is prompted for information step-by-step. If a mistake is made in an early step, the only way to correct it is to terminate the script and restart the entire process from the beginning. This makes the workflow inflexible and unforgiving. The goal is to create a system where the user can "advance and retreat freely" (`进退自如`).

## 2. Proposed Solution: Stateful, Menu-Driven Application

The recommended solution is to refactor the script from a linear sequence of function calls into a stateful, interactive, menu-driven application.

### Core Concepts

*   **Stateful "Workflow Manager":** The architecture will be centered around a Python class that manages the application's state. This class will hold all user-provided metadata (package name, file paths, etc.) in a single, persistent object throughout the session.
*   **Interactive Main Menu:** The script will run in a continuous loop. In each iteration, it will display the current configuration and a menu of available actions.
*   **Independent, Re-runnable Actions:** Each step (e.g., editing metadata, generating a file) will be a distinct action that can be selected from the menu. The user can run these actions in any order and can re-run them to correct or change data.

### Example Workflow

**Initial Run (No Data Entered):**
When the script first starts, the configuration will show as empty, clearly indicating what information is needed.

```
--- BSgenome Interactive Builder ---

Current Configuration:
- Package Name: (not set)
- Organism: (not set)
- FASTA File: (not set)
- ... (all other fields will also show as 'not set') ...

What would you like to do?
[1] Edit organism and package metadata
[2] Set source file paths
[3] Generate the .seed file
[4] Convert FASTA to .2bit format
[5] --- RUN THE FINAL BUILD AND INSTALL ---
[6] Exit
```

**After Entering Data:**
As the user completes steps, the configuration display updates. They can then choose to either proceed to the next step or go back to a previous one to make changes.

```
--- BSgenome Interactive Builder ---

Current Configuration:
- Package Name: BSgenome.Aluchuensis.NCBI.IFO4308
- Organism: Aspergillus luchuensis
- FASTA File: GCF_016861625.1_AkawachiiIFO4308_assembly01_genomic.fna
- ... (other data) ...

What would you like to do?
[1] Edit organism and package metadata
[2] Set source file paths
[3] Generate the .seed file
[4] Convert FASTA to .2bit format
[5] --- RUN THE FINAL BUILD AND INSTALL ---
[6] Exit
```

This design directly addresses the request for a flexible workflow, allowing the user to easily move between steps and correct information without restarting.