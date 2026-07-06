#!/usr/bin/env python3
"""Generate the compact package browser catalog.

The public package browser keeps catalog rows intentionally small:

  { "a": accession, "o": organism, "m": assembly, "g": group,
    "s": source, "z": genome_size_mb }

This script refreshes NCBI RefSeq rows from current assembly_summary files and
preserves non-NCBI rows from the existing catalog, such as curated Ensembl
entries.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Iterable


def clean_organism(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def iter_summary(path: Path) -> Iterable[dict[str, str]]:
    with path.open() as handle:
        for line in handle:
            if line.startswith("#assembly_accession"):
                headers = line.lstrip("#").rstrip("\n").split("\t")
                break
        else:
            raise ValueError(f"no assembly_summary header found in {path}")
        yield from csv.DictReader(handle, fieldnames=headers, delimiter="\t")


ALLOWED_GROUPS = {
    "archaea",
    "bacteria",
    "fungi",
    "invertebrate",
    "plant",
    "protozoa",
    "vertebrate_mammalian",
    "vertebrate_other",
    "viral",
}


def include_refseq_row(row: dict[str, str]) -> bool:
    if row.get("version_status") != "latest":
        return False
    group = row.get("group", "").strip()
    if group not in ALLOWED_GROUPS:
        return False
    if group == "viral":
        # Viral RefSeq records usually do not carry the representative/reference
        # category used for cellular genomes, but the existing catalog includes
        # them as discoverable public assemblies.
        return True
    return row.get("refseq_category") in {"reference genome", "representative genome"}


def catalog_row(row: dict[str, str], source: str) -> dict[str, object] | None:
    if source == "ncbi" and not include_refseq_row(row):
        return None

    accession = row.get("assembly_accession", "").strip()
    organism = clean_organism(row.get("organism_name", ""))
    assembly = row.get("asm_name", "").strip()
    group = row.get("group", "").strip()
    if not accession or not organism or not assembly or not group:
        return None

    genome_size = int(row.get("genome_size", "0") or "0")
    compact: dict[str, object] = {
        "a": accession,
        "o": organism,
        "m": assembly,
        "g": group,
        "s": source,
    }
    if genome_size > 0:
        compact["z"] = round(genome_size / 1_000_000, 1)
    return compact


def row_key(row: dict[str, object]) -> tuple[str, str]:
    accession = str(row.get("a") or "")
    if accession:
        return ("accession", accession)
    return (
        "fallback",
        "|".join(str(row.get(key) or "") for key in ("o", "m", "s")),
    )


def load_existing(path: Path | None) -> list[dict[str, object]]:
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"existing catalog must be a list: {path}")
    return [row for row in data if isinstance(row, dict)]


def sort_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(row.get("o") or "").lower(),
        str(row.get("s") or ""),
        str(row.get("m") or "").lower(),
        str(row.get("a") or ""),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing-catalog", type=Path)
    parser.add_argument("--refseq-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    by_key: dict[tuple[str, str], dict[str, object]] = {}

    for row in load_existing(args.existing_catalog):
        # Preserve curated non-NCBI rows. NCBI rows are regenerated below from
        # current assembly_summary files so accession versions and sizes stay fresh.
        if str(row.get("s") or "").lower() == "ncbi":
            continue
        by_key[row_key(row)] = row

    for summary_row in iter_summary(args.refseq_summary):
        row = catalog_row(summary_row, "ncbi")
        if not row:
            continue
        by_key[row_key(row)] = row

    catalog = sorted(by_key.values(), key=sort_key)
    args.output.write_text(json.dumps(catalog, separators=(",", ":")) + "\n")

    groups: dict[str, int] = {}
    sources: dict[str, int] = {}
    for row in catalog:
        groups[str(row.get("g") or "other")] = groups.get(str(row.get("g") or "other"), 0) + 1
        sources[str(row.get("s") or "unknown")] = sources.get(str(row.get("s") or "unknown"), 0) + 1

    print(f"Wrote {len(catalog)} catalog rows to {args.output}")
    print("Sources:", dict(sorted(sources.items())))
    print("Groups:", dict(sorted(groups.items())))


if __name__ == "__main__":
    main()
