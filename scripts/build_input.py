#!/usr/bin/env python3
"""Validate workflow metadata and write a BSgenome seed without shell evaluation."""

import argparse
import os
import re
import sys
from pathlib import Path


def validate_fields(fields):
    result = {}
    for name, value in fields.items():
        if value is None:
            value = ""
        if not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"{name} must be a scalar value")
        value = str(value)
        if any(ord(char) < 32 or ord(char) == 127 or char in "\u2028\u2029" for char in value):
            raise ValueError(f"{name} must be a single line without control characters")
        result[name] = value

    # These identifiers also become file paths, Git tags, and an R object name.
    patterns = {
        "package_name": r"BSgenome\.[A-Za-z][A-Za-z0-9]*\.[A-Za-z][A-Za-z0-9]*\.[A-Za-z0-9]+",
        "version": r"[0-9]+(?:[.-][0-9]+)+",
        "job_id": r"[A-Za-z0-9_-]+",
    }
    for name, pattern in patterns.items():
        if name in result and not re.fullmatch(pattern, result[name]):
            raise ValueError(f"invalid {name}")
    return result


def complete_ensembl_identity(fields, lookup=None):
    """Keep genome optional for API clients while recording a verified assembly."""
    if fields.get("fasta_source") != "ensembl" or fields.get("genome", "").strip():
        return fields
    if lookup is None:
        from resolve_ensembl_fasta import fetch_assembly_metadata
        lookup = fetch_assembly_metadata
    metadata = lookup(fields.get("species_url", ""))
    assembly = metadata.get("assembly_name")
    accession = metadata.get("assembly_accession") or ""
    if not isinstance(assembly, str) or not assembly.strip():
        raise ValueError("Ensembl metadata did not identify the assembly")
    if fields.get("accession") and fields["accession"] != accession:
        raise ValueError("requested accession does not match the current Ensembl assembly")
    return dict(fields, genome=assembly, accession=accession)


def write_seed(environment):
    names = (
        "package_name", "title", "description", "organism", "common_name", "genome",
        "provider", "release_date", "version", "source_url",
    )
    fields = validate_fields({name: environment.get(f"BUILD_PARAM_{name.upper()}", "") for name in names})
    package = fields["package_name"]
    organism = fields["organism"]
    provider = fields["provider"]
    genome = fields["genome"]
    seed = {
        "Package": package,
        "Title": fields["title"] or f"Full genome sequences for {organism} ({provider} version {genome})",
        "Description": fields["description"] or (
            f"Full genome sequences for {organism} ({fields['common_name']}) "
            f"as provided by {provider} ({genome}, {fields['release_date']}) "
            "and stored in Biostrings objects."
        ),
        "Version": fields["version"],
        "organism": organism,
        "common_name": fields["common_name"],
        "genome": genome,
        "provider": provider,
        "release_date": fields["release_date"],
        "source_url": fields["source_url"],
        "organism_biocview": organism.replace(" ", "_"),
        "BSgenomeObjname": package.split(".")[1],
        "circ_seqs": "character(0)",
        "seqs_srcdir": str(Path.cwd()),
        "seqfile_name": "genome.2bit",
    }
    text = "".join(f"{name}: {value}\n" for name, value in seed.items())
    Path(f"{package}.seed").write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rewrite-forged-metadata", type=Path)
    parser.add_argument("--prepare-forge-seed", type=Path)
    args = parser.parse_args()
    try:
        if args.rewrite_forged_metadata or args.prepare_forge_seed:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from autoBSgenome import prepare_forge_seed, rewrite_forged_metadata
            if args.prepare_forge_seed:
                prepare_forge_seed(args.prepare_forge_seed, Path.cwd())
            else:
                rewrite_forged_metadata(args.rewrite_forged_metadata, Path.cwd())
        else:
            write_seed(os.environ)
    except ValueError as exc:
        print(f"ERROR: invalid build metadata: {exc}", file=sys.stderr)
        raise SystemExit(1)
