#!/usr/bin/env python3
"""Generate a validated Ensembl catalog snapshot from release species TSVs."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
from pathlib import Path


DIVISION_GROUPS = {
    "vertebrates": "vertebrate_other",
    "bacteria": "bacteria",
    "fungi": "fungi",
    "metazoa": "metazoa",
    "plants": "plants",
    "protists": "protists",
}

DEFAULT_MINIMUMS = {
    "vertebrates": 100,
    "bacteria": 1_000,
    "fungi": 100,
    "metazoa": 100,
    "plants": 100,
    "protists": 100,
}


def key_value(value: str) -> tuple[str, str]:
    key, separator, raw = value.partition("=")
    if not separator or not key or not raw:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {value!r}")
    return key, raw


def scientific_name(display_name: str, species_slug: str, division: str) -> str:
    if division == "vertebrates":
        parts = species_slug.split("_")
        if not parts:
            return display_name.strip()
        return " ".join([parts[0].capitalize(), *parts[1:]])
    return re.sub(r"\s*\(GC[AF]_\d+\)\s*$", "", display_name).strip()


def open_text(path: Path):
    return gzip.open(path, "rt") if path.suffix == ".gz" else path.open()


def load_assembly_summaries(
    paths: list[Path], wanted_accessions: set[str]
) -> dict[str, dict[str, str]]:
    summaries: dict[str, dict[str, str]] = {}
    for path in paths:
        with open_text(path) as handle:
            for line in handle:
                if line.lstrip("# ").startswith("assembly_accession\t"):
                    fieldnames = line.lstrip("# ").rstrip("\n").split("\t")
                    break
            else:
                raise ValueError(f"missing assembly_summary header: {path}")
            for row in csv.DictReader(handle, fieldnames=fieldnames, delimiter="\t"):
                accession = (row.get("assembly_accession") or "").strip()
                if accession in wanted_accessions:
                    summaries[accession] = row
    return summaries


def parse_source(
    path: Path,
    division: str,
    release: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open() as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            raise ValueError(f"missing TSV header: {path}")
        reader.fieldnames = [name.lstrip("#") for name in reader.fieldnames]
        required = {"name", "species", "assembly", "assembly_accession"}
        missing = required.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"missing columns in {path}: {', '.join(sorted(missing))}")
        for raw in reader:
            species = (raw.get("species") or "").strip()
            assembly = (raw.get("assembly") or "").strip()
            if not species or not assembly:
                continue
            accession = (raw.get("assembly_accession") or "").strip()
            row: dict[str, object] = {
                "a": accession,
                "o": scientific_name(raw.get("name") or "", species, division),
                "m": assembly,
                "g": DIVISION_GROUPS[division],
                "s": "ensembl",
                "e": species,
                "d": division,
                "r": release,
            }
            rows.append(row)
    return rows


def row_key(row: dict[str, object]) -> tuple[str, str]:
    group = str(row.get("g") or "")
    inferred_division = {
        "vertebrate_mammalian": "vertebrates",
        "vertebrate_other": "vertebrates",
    }.get(group, group)
    division = str(row.get("d") or inferred_division)
    accession = str(row.get("a") or "")
    return (
        division,
        accession
        or str(row.get("e") or "")
        or "|".join(str(row.get(key) or "") for key in ("o", "m")),
    )


def serialized_key(row: dict[str, object]) -> str:
    division, identity = row_key(row)
    return f"{division}|{identity}"


def load_rows(path: Path | None) -> list[dict[str, object]]:
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"expected a JSON array: {path}")
    return [row for row in data if isinstance(row, dict)]


def load_state(path: Path | None) -> dict[str, object]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", default=[], type=key_value)
    parser.add_argument("--minimum", action="append", default=[], type=key_value)
    parser.add_argument("--release-main", required=True, type=int)
    parser.add_argument("--release-genomes", required=True, type=int)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--assembly-summary", action="append", default=[], type=Path)
    parser.add_argument("--drop-threshold", type=float, default=0.10)
    parser.add_argument("--allow-large-drop", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--state-output", required=True, type=Path)
    args = parser.parse_args()

    sources = dict(args.source)
    minimums = {**DEFAULT_MINIMUMS, **{key: int(value) for key, value in args.minimum}}
    unknown = set(sources).difference(DIVISION_GROUPS)
    if unknown:
        raise SystemExit(f"ERROR: unknown divisions: {', '.join(sorted(unknown))}")

    rows: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    previous_state = load_state(args.state)
    previous_counts = previous_state.get("counts")
    if not isinstance(previous_counts, dict):
        previous_counts = {}
    for division, raw_path in sources.items():
        release = args.release_main if division == "vertebrates" else args.release_genomes
        parsed = parse_source(Path(raw_path), division, release)
        counts[division] = len(parsed)
        minimum = minimums.get(division, 1)
        if len(parsed) < minimum:
            raise SystemExit(
                f"ERROR: {division} returned {len(parsed)} rows; minimum is {minimum}"
            )
        previous_count = int(previous_counts.get(division, 0))
        if (
            not args.allow_large_drop
            and previous_count > 0
            and len(parsed) < previous_count * (1 - args.drop_threshold)
        ):
            drop_percent = round((previous_count - len(parsed)) / previous_count * 100, 1)
            raise SystemExit(
                f"ERROR: {division} dropped {drop_percent}% "
                f"({previous_count} -> {len(parsed)}); refusing to publish"
            )
        rows.extend(parsed)

    wanted_accessions = {str(row.get("a") or "") for row in rows if row.get("a")}
    assembly_summaries = load_assembly_summaries(
        args.assembly_summary, wanted_accessions
    )
    for row in rows:
        summary = assembly_summaries.get(str(row.get("a") or ""), {})
        organism_name = (summary.get("organism_name") or "").strip()
        if organism_name:
            row["o"] = organism_name
        genome_size = int(summary.get("genome_size", "0") or "0")
        if genome_size > 0:
            row["z"] = round(genome_size / 1_000_000, 1)

    by_key: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = row_key(row)
        if key in by_key:
            raise SystemExit(f"ERROR: duplicate Ensembl row: {key}")
        by_key[key] = row

    prior_missing = previous_state.get("missing_counts")
    if not isinstance(prior_missing, dict):
        prior_missing = {}
    next_missing: dict[str, int] = {}
    fetched_divisions = set(sources)
    for previous_row in load_rows(args.previous):
        if str(previous_row.get("s") or "").lower() != "ensembl":
            continue
        key = row_key(previous_row)
        division = key[0]
        if key in by_key:
            continue
        if division not in fetched_divisions:
            by_key[key] = previous_row
            continue
        state_key = serialized_key(previous_row)
        missing_count = int(prior_missing.get(state_key, 0)) + 1
        if missing_count < 2:
            by_key[key] = previous_row
            next_missing[state_key] = missing_count

    output_rows = sorted(
        by_key.values(),
        key=lambda row: (
            str(row.get("o") or "").lower(),
            str(row.get("d") or ""),
            str(row.get("a") or ""),
        ),
    )
    args.output.write_text(json.dumps(output_rows, separators=(",", ":")) + "\n")
    args.state_output.write_text(
        json.dumps(
            {
                "version": 1,
                "releases": {
                    "vertebrates": args.release_main,
                    "ensembl_genomes": args.release_genomes,
                },
                "counts": counts,
                "missing_counts": next_missing,
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    print(f"Wrote {len(output_rows)} Ensembl rows")
    print("Divisions:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
