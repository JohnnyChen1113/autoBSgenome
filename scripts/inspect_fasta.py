#!/usr/bin/env python3
"""Collect FASTA build metadata with bounded validation for custom inputs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


CHUNK_SIZE = 16 * 1024 * 1024
PREFIX_SCAN_BYTES = 8 * 1024 * 1024
SAMPLE_LIMIT_BASES = 1_000_000
OFFICIAL_SOURCES = {"ncbi", "ensembl"}
CUSTOM_SOURCES = {"url", "upload"}
NUCLEOTIDE_BYTES = set(b"ACGTUNRYSWKMBDHVacgtunryswkmbdhv.-")
PROTEIN_ONLY_BYTES = set(b"EFILPQZJXO*efilpqzjxo*")


def inspect_prefix(path: Path, validate_bases: bool) -> int:
    """Check basic structure and optionally sample custom-input characters."""
    with path.open("rb") as handle:
        prefix = handle.read(PREFIX_SCAN_BYTES)

    if not prefix:
        raise ValueError("file is empty")

    saw_header = False
    saw_sequence = False
    sampled_bases = 0
    invalid_bytes: set[int] = set()
    protein_bytes: set[int] = set()

    for raw_line in prefix.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if not saw_header:
            if line.startswith(b"@"):
                raise ValueError("file starts with @ and looks like FASTQ, not FASTA")
            if not line.startswith(b">"):
                raise ValueError("sequence data appears before the first FASTA header")

        if line.startswith(b">"):
            saw_header = True
            continue

        if not saw_header:
            raise ValueError("sequence data appears before the first FASTA header")

        sequence = b"".join(line.split())
        if not sequence:
            continue
        saw_sequence = True

        if not validate_bases:
            break

        remaining = SAMPLE_LIMIT_BASES - sampled_bases
        if remaining <= 0:
            break
        sample = sequence[:remaining]
        sampled_bases += len(sample)
        invalid = set(sample) - NUCLEOTIDE_BYTES
        invalid_bytes.update(invalid)
        protein_bytes.update(invalid & PROTEIN_ONLY_BYTES)
        if sampled_bases >= SAMPLE_LIMIT_BASES:
            break

    if not saw_header:
        raise ValueError("no FASTA headers were found in the inspection prefix")
    if not saw_sequence:
        raise ValueError("no FASTA sequence data was found in the inspection prefix")
    if invalid_bytes:
        characters = " ".join(
            chr(value) if 32 <= value <= 126 else f"0x{value:02x}"
            for value in sorted(invalid_bytes)[:20]
        )
        if protein_bytes:
            raise ValueError(
                "file looks like protein FASTA, not nucleotide FASTA; "
                f"invalid sampled characters: {characters}"
            )
        raise ValueError(f"invalid sampled nucleotide FASTA characters: {characters}")

    return sampled_bases if validate_bases else 0


def _finish_header(fragment: bytes) -> tuple[bytes, bool]:
    match = re.search(rb"\s", fragment)
    if match:
        return fragment[: match.start()], True
    return fragment, False


def scan_metadata(path: Path) -> tuple[int, list[str]]:
    """Count records and capture the first five IDs in one chunked full scan."""
    seq_count = 0
    seq_ids: list[str] = []
    previous_byte: bytes | None = None
    first_chunk = True
    pending_header: bytes | None = None

    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            if first_chunk and chunk.startswith(b">"):
                seq_count += 1
            elif previous_byte == b"\n" and chunk.startswith(b">"):
                seq_count += 1
            seq_count += chunk.count(b"\n>")

            if len(seq_ids) < 5:
                if pending_header is not None:
                    continuation, complete = _finish_header(chunk)
                    pending_header += continuation
                    if complete:
                        if not pending_header:
                            raise ValueError("a FASTA header has no sequence ID")
                        seq_ids.append(pending_header.decode("utf-8", errors="replace"))
                        pending_header = None

                prefix = b"\n" if (first_chunk or previous_byte == b"\n") else b""
                probe = prefix + chunk
                position = 0
                while len(seq_ids) < 5:
                    marker = probe.find(b"\n>", position)
                    if marker < 0:
                        break
                    header_start = marker + 2
                    fragment, complete = _finish_header(probe[header_start:])
                    if complete:
                        if not fragment:
                            raise ValueError("a FASTA header has no sequence ID")
                        seq_ids.append(fragment.decode("utf-8", errors="replace"))
                    else:
                        pending_header = fragment
                    position = header_start + max(len(fragment), 1)

            previous_byte = chunk[-1:]
            first_chunk = False

    if pending_header is not None and len(seq_ids) < 5:
        if not pending_header:
            raise ValueError("a FASTA header has no sequence ID")
        seq_ids.append(pending_header.decode("utf-8", errors="replace"))
    if seq_count == 0:
        raise ValueError("no FASTA headers were found")
    if not seq_ids:
        raise ValueError("no FASTA sequence IDs were found")
    return seq_count, seq_ids


def inspect(path: Path, source: str) -> dict:
    if not path.is_file():
        raise ValueError(f"file does not exist: {path}")

    validate_bases = source in CUSTOM_SOURCES
    sampled_bases = inspect_prefix(path, validate_bases=validate_bases)
    seq_count, seq_ids = scan_metadata(path)
    return {
        "source": source,
        "inspection_mode": "prefix-sampled" if validate_bases else "metadata-only",
        "exhaustive_validation": False,
        "sample_limit_bases": SAMPLE_LIMIT_BASES if validate_bases else 0,
        "sampled_bases": sampled_bases,
        "seq_count": seq_count,
        "seq_ids": seq_ids,
        "fasta_size_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fasta", type=Path)
    parser.add_argument(
        "--source",
        required=True,
        choices=sorted(OFFICIAL_SOURCES | CUSTOM_SOURCES),
    )
    parser.add_argument("--json", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    try:
        report = inspect(args.fasta, args.source)
    except Exception as exc:
        print(f"ERROR: FASTA inspection failed: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(report, sort_keys=True)
    print(text)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"seq_ids={','.join(report['seq_ids'])}\n")
            handle.write(f"seq_count={report['seq_count']}\n")
            handle.write(f"fasta_size={report['fasta_size_bytes']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
