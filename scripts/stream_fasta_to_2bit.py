#!/usr/bin/env python3
"""Inspect a gzipped FASTA stream while feeding it to faToTwoBit."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from inspect_fasta import CHUNK_SIZE, FastaStreamInspector

VALID_SOURCES = {"ncbi", "ensembl", "url", "upload"}


class HashingReader:
    def __init__(self, raw) -> None:
        self.raw = raw
        self.md5 = hashlib.md5()
        self.byte_count = 0

    def read(self, size: int = -1) -> bytes:
        data = self.raw.read(size)
        self.md5.update(data)
        self.byte_count += len(data)
        return data


def write_outputs(report: dict, json_path: Path | None, github_output: Path | None) -> None:
    text = json.dumps(report, sort_keys=True)
    print(text)
    if json_path:
        json_path.write_text(text + "\n", encoding="utf-8")
    if github_output:
        with github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"seq_ids={','.join(report['seq_ids'])}\n")
            handle.write(f"seq_count={report['seq_count']}\n")
            handle.write(f"fasta_size={report['fasta_size_bytes']}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, choices=sorted(VALID_SOURCES))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-md5", required=True)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--converter", default="faToTwoBit")
    parser.add_argument("--long", action="store_true")
    args = parser.parse_args()

    output = args.output
    output.unlink(missing_ok=True)
    command = [args.converter]
    if args.long:
        command.append("-long")
    command.extend(["stdin", str(output)])

    process: subprocess.Popen | None = None
    wall_started = time.monotonic()
    python_cpu_started = time.process_time()
    child_usage_started = resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        hashing_reader = HashingReader(sys.stdin.buffer)
        inspector = FastaStreamInspector(args.source)
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        assert process.stdin is not None
        with gzip.GzipFile(fileobj=hashing_reader, mode="rb") as fasta_stream:
            while chunk := fasta_stream.read(CHUNK_SIZE):
                inspector.feed(chunk)
                process.stdin.write(chunk)
        process.stdin.close()
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"faToTwoBit exited with status {return_code}")

        actual_md5 = hashing_reader.md5.hexdigest()
        if actual_md5.lower() != args.expected_md5.lower():
            raise ValueError(
                f"compressed MD5 mismatch: expected {args.expected_md5.lower()}, "
                f"got {actual_md5.lower()}"
            )
        report = inspector.finish()
        report["compressed_size_bytes"] = hashing_reader.byte_count
        report["compressed_md5"] = actual_md5
        report["twobit_size_bytes"] = output.stat().st_size
        child_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        converter_user_cpu = max(
            0.0, child_usage.ru_utime - child_usage_started.ru_utime
        )
        converter_system_cpu = max(
            0.0, child_usage.ru_stime - child_usage_started.ru_stime
        )
        report["timings_sec"] = {
            "pipeline_wall": round(max(0.0, time.monotonic() - wall_started), 3),
            "python_cpu": round(max(0.0, time.process_time() - python_cpu_started), 3),
            "converter_cpu": round(converter_user_cpu + converter_system_cpu, 3),
            "converter_user_cpu": round(converter_user_cpu, 3),
            "converter_system_cpu": round(converter_system_cpu, 3),
        }
        write_outputs(report, args.json, args.github_output)
        return 0
    except Exception as exc:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
        output.unlink(missing_ok=True)
        if args.json:
            args.json.unlink(missing_ok=True)
        print(f"ERROR: streaming FASTA conversion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
