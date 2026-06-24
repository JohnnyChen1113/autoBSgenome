#!/usr/bin/env python3
"""Validate that a FASTA file contains nucleotide sequences."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


NUCLEOTIDE_CHARS = set("ACGTUNRYSWKMBDHVacgtunryswkmbdhv.-")
PROTEIN_ONLY_CHARS = set("EFILPQZJXO*efilpqzjxo*")


def validate(path: Path) -> dict:
    seq_count = 0
    total_bases = 0
    current_bases = 0
    longest_seq = 0
    invalid_chars: set[str] = set()
    protein_chars: set[str] = set()
    saw_sequence = False

    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if line_no == 1 and line.startswith("\ufeff"):
                line = line.lstrip("\ufeff")

            if line.startswith("@") and seq_count == 0:
                raise ValueError("file starts with @ and looks like FASTQ, not FASTA")

            if line.startswith(">"):
                if seq_count > 0:
                    longest_seq = max(longest_seq, current_bases)
                seq_count += 1
                current_bases = 0
                continue

            if seq_count == 0:
                raise ValueError(f"sequence data appears before the first FASTA header at line {line_no}")

            for char in "".join(line.split()):
                if char not in NUCLEOTIDE_CHARS:
                    invalid_chars.add(char)
                if char in PROTEIN_ONLY_CHARS:
                    protein_chars.add(char)
                total_bases += 1
                current_bases += 1
                saw_sequence = True

    if seq_count > 0:
        longest_seq = max(longest_seq, current_bases)
    if seq_count == 0:
        raise ValueError("no FASTA headers were found")
    if not saw_sequence:
        raise ValueError("no FASTA sequence data was found")
    if invalid_chars:
        chars = " ".join(sorted(invalid_chars)[:20])
        if protein_chars:
            raise ValueError(
                f"file looks like protein FASTA, not nucleotide FASTA; invalid nucleotide characters: {chars}"
            )
        raise ValueError(f"invalid nucleotide FASTA characters: {chars}")

    return {
        "seq_count": seq_count,
        "total_bases": total_bases,
        "longest_seq": longest_seq,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fasta", type=Path)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    try:
        stats = validate(args.fasta)
    except Exception as exc:
        print(f"ERROR: invalid nucleotide FASTA: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(stats, sort_keys=True)
    print(text)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
