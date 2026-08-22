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


def inspect_prefix(prefix: bytes, validate_bases: bool) -> int:
    """Check basic structure and optionally sample custom-input characters."""
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


class FastaStreamInspector:
    """Incrementally inspect FASTA bytes without retaining the full assembly."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.fasta_size = 0
        self.seq_count = 0
        self.seq_ids: list[str] = []
        self.previous_byte: bytes | None = None
        self.first_chunk = True
        self.pending_header: bytes | None = None
        self.prefix = bytearray()

    def feed(self, chunk: bytes) -> None:
        self.fasta_size += len(chunk)
        if len(self.prefix) < PREFIX_SCAN_BYTES:
            remaining = PREFIX_SCAN_BYTES - len(self.prefix)
            self.prefix.extend(chunk[:remaining])

        if self.first_chunk and chunk.startswith(b">"):
            self.seq_count += 1
        elif self.previous_byte == b"\n" and chunk.startswith(b">"):
            self.seq_count += 1
        self.seq_count += chunk.count(b"\n>")

        if len(self.seq_ids) < 5:
            if self.pending_header is not None:
                continuation, complete = _finish_header(chunk)
                self.pending_header += continuation
                if complete:
                    self._append_header(self.pending_header)
                    self.pending_header = None

            prefix = b"\n" if (self.first_chunk or self.previous_byte == b"\n") else b""
            probe = prefix + chunk
            position = 0
            while len(self.seq_ids) < 5:
                marker = probe.find(b"\n>", position)
                if marker < 0:
                    break
                header_start = marker + 2
                fragment, complete = _finish_header(probe[header_start:])
                if complete:
                    self._append_header(fragment)
                else:
                    self.pending_header = fragment
                position = header_start + max(len(fragment), 1)

        self.previous_byte = chunk[-1:]
        self.first_chunk = False

    def _append_header(self, header: bytes) -> None:
        if not header:
            raise ValueError("a FASTA header has no sequence ID")
        self.seq_ids.append(header.decode("utf-8", errors="replace"))

    def finish(self) -> dict:
        if self.pending_header is not None and len(self.seq_ids) < 5:
            self._append_header(self.pending_header)
        sampled_bases = inspect_prefix(
            bytes(self.prefix), validate_bases=self.source in CUSTOM_SOURCES
        )
        if self.seq_count == 0:
            raise ValueError("no FASTA headers were found")
        if not self.seq_ids:
            raise ValueError("no FASTA sequence IDs were found")
        return {
            "source": self.source,
            "inspection_mode": (
                "prefix-sampled" if self.source in CUSTOM_SOURCES else "metadata-only"
            ),
            "exhaustive_validation": False,
            "sample_limit_bases": (
                SAMPLE_LIMIT_BASES if self.source in CUSTOM_SOURCES else 0
            ),
            "sampled_bases": sampled_bases,
            "seq_count": self.seq_count,
            "seq_ids": self.seq_ids,
            "fasta_size_bytes": self.fasta_size,
        }


def inspect(path: Path, source: str) -> dict:
    if not path.is_file():
        raise ValueError(f"file does not exist: {path}")

    inspector = FastaStreamInspector(source)
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            inspector.feed(chunk)
    return inspector.finish()


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
