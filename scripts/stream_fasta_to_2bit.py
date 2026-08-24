#!/usr/bin/env python3
"""Inspect a gzip or plain FASTA stream while feeding it to faToTwoBit."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

from inspect_fasta import CHUNK_SIZE, FastaStreamInspector

VALID_SOURCES = {"ncbi", "ensembl", "url", "upload"}
LONG_FORMAT_RETRY_EXIT_CODE = 75
CONVERTER_FAILURE_EXIT_CODE = 76


class LongFormatRequired(RuntimeError):
    pass


class ConverterFailed(RuntimeError):
    pass


def read_cgroup_oom_kills() -> int | None:
    """Return this cgroup's OOM-kill count when Linux exposes it."""
    for path in (
        Path("/sys/fs/cgroup/memory.events.local"),
        Path("/sys/fs/cgroup/memory.events"),
    ):
        try:
            values = dict(
                line.split(maxsplit=1)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            if "oom_kill" in values:
                return int(values["oom_kill"])
        except (OSError, ValueError):
            continue
    return None


def collect_converter_result(
    process: subprocess.Popen,
) -> tuple[int, bytes]:
    """Close converter input, wait for it, and retain its real failure."""
    if process.stdin is not None and not process.stdin.closed:
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass
    converter_stderr = b""
    if process.stderr is not None:
        converter_stderr = process.stderr.read()
    return process.wait(), converter_stderr


def describe_converter_failure(
    return_code: int, oom_kills_before: int | None, oom_kills_after: int | None
) -> str:
    if return_code < 0:
        signal_number = -return_code
        try:
            signal_name = signal.Signals(signal_number).name
        except ValueError:
            signal_name = f"signal {signal_number}"
        if signal_number == signal.SIGKILL:
            if (
                oom_kills_before is not None
                and oom_kills_after is not None
                and oom_kills_after > oom_kills_before
            ):
                return (
                    f"faToTwoBit terminated by {signal_name}; cgroup oom_kill "
                    f"increased from {oom_kills_before} to {oom_kills_after} "
                    "(out of memory)"
                )
            return (
                f"faToTwoBit terminated by {signal_name} "
                "(possible out-of-memory kill)"
            )
        return f"faToTwoBit terminated by {signal_name}"
    return f"faToTwoBit exited with status {return_code}"


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


class PrefixReader:
    """Replay bytes used for format detection, then continue from the input."""

    def __init__(self, prefix: bytes, raw) -> None:
        self.prefix = prefix
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            data = self.prefix + self.raw.read()
            self.prefix = b""
            return data
        if not self.prefix:
            return self.raw.read(size)
        data = self.prefix[:size]
        self.prefix = self.prefix[size:]
        if len(data) < size:
            data += self.raw.read(size - len(data))
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
    parser.add_argument("--expected-md5")
    parser.add_argument(
        "--compression", choices=("auto", "gzip", "plain"), default="gzip"
    )
    parser.add_argument("--json", type=Path)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--converter", default="faToTwoBit")
    parser.add_argument("--long", action="store_true")
    args = parser.parse_args()
    if args.source == "ncbi" and not args.expected_md5:
        parser.error("--expected-md5 is required for NCBI input")

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
    oom_kills_before = read_cgroup_oom_kills()
    try:
        hashing_reader = HashingReader(sys.stdin.buffer)
        inspector = FastaStreamInspector(args.source)
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stderr=subprocess.PIPE
        )
        assert process.stdin is not None
        assert process.stderr is not None
        prefix = hashing_reader.read(2)
        compression = args.compression
        if compression == "auto":
            compression = "gzip" if prefix == b"\x1f\x8b" else "plain"
        input_stream = PrefixReader(prefix, hashing_reader)
        fasta_stream = (
            gzip.GzipFile(fileobj=input_stream, mode="rb")
            if compression == "gzip"
            else input_stream
        )
        with fasta_stream:
            while chunk := fasta_stream.read(CHUNK_SIZE):
                inspector.feed(chunk)
                try:
                    process.stdin.write(chunk)
                except BrokenPipeError:
                    return_code, converter_stderr = collect_converter_result(process)
                    if converter_stderr:
                        sys.stderr.buffer.write(converter_stderr)
                    raise ConverterFailed(
                        describe_converter_failure(
                            return_code,
                            oom_kills_before,
                            read_cgroup_oom_kills(),
                        )
                    ) from None
        return_code, converter_stderr = collect_converter_result(process)
        if converter_stderr:
            sys.stderr.buffer.write(converter_stderr)
        if return_code != 0:
            if not args.long and (
                b"index overflow" in converter_stderr
                or b"use -long option" in converter_stderr
            ):
                raise LongFormatRequired("faToTwoBit requires 64-bit index offsets")
            raise ConverterFailed(
                describe_converter_failure(
                    return_code,
                    oom_kills_before,
                    read_cgroup_oom_kills(),
                )
            )

        actual_md5 = hashing_reader.md5.hexdigest()
        if args.expected_md5 and actual_md5.lower() != args.expected_md5.lower():
            input_kind = "compressed" if compression == "gzip" else "input"
            raise ValueError(
                f"{input_kind} MD5 mismatch: expected {args.expected_md5.lower()}, "
                f"got {actual_md5.lower()}"
            )
        report = inspector.finish()
        report["input_compression"] = compression
        report["input_size_bytes"] = hashing_reader.byte_count
        report["input_md5"] = actual_md5
        if compression == "gzip":
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
    except LongFormatRequired as exc:
        output.unlink(missing_ok=True)
        if args.json:
            args.json.unlink(missing_ok=True)
        print(f"LONG_2BIT_REQUIRED: {exc}", file=sys.stderr)
        return LONG_FORMAT_RETRY_EXIT_CODE
    except ConverterFailed as exc:
        output.unlink(missing_ok=True)
        if args.json:
            args.json.unlink(missing_ok=True)
        print(f"CONVERTER_FAILED: {exc}", file=sys.stderr)
        return CONVERTER_FAILURE_EXIT_CODE
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
