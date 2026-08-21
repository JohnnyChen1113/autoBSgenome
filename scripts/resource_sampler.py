#!/usr/bin/env python3
"""Sample disk and container memory while a workflow stage is running."""

import argparse
import json
import os
import pathlib
import shutil
import signal
import tempfile
import time


def _max(current, candidate):
    return max(int(current or 0), int(candidate or 0))


def record_peaks(
    metrics_path,
    stage,
    *,
    disk_used_bytes,
    memory_used_bytes,
    process_rss_bytes,
    samples,
):
    """Merge sampled peaks into the shared build metrics document."""
    path = pathlib.Path(metrics_path)
    metrics = json.loads(path.read_text()) if path.exists() else {}
    peaks = metrics.setdefault("resource_peaks", {})
    peaks["disk_used_bytes"] = _max(
        peaks.get("disk_used_bytes"), disk_used_bytes
    )
    peaks["memory_used_bytes"] = _max(
        peaks.get("memory_used_bytes"), memory_used_bytes
    )
    peaks["process_rss_bytes"] = _max(
        peaks.get("process_rss_bytes"), process_rss_bytes
    )
    stage_peaks = peaks.setdefault("stages", {}).setdefault(stage, {})
    stage_peaks["disk_used_bytes"] = _max(
        stage_peaks.get("disk_used_bytes"), disk_used_bytes
    )
    stage_peaks["memory_used_bytes"] = _max(
        stage_peaks.get("memory_used_bytes"), memory_used_bytes
    )
    stage_peaks["process_rss_bytes"] = _max(
        stage_peaks.get("process_rss_bytes"), process_rss_bytes
    )
    stage_peaks["samples"] = int(stage_peaks.get("samples", 0)) + int(samples)

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as handle:
        json.dump(metrics, handle, separators=(",", ":"))
        temporary_path = handle.name
    os.replace(temporary_path, path)


def memory_used_bytes():
    for candidate in (
        "/sys/fs/cgroup/memory.current",
        "/sys/fs/cgroup/memory/memory.usage_in_bytes",
    ):
        try:
            return int(pathlib.Path(candidate).read_text().strip())
        except (FileNotFoundError, PermissionError, ValueError):
            continue
    return 0


def process_rss_bytes():
    total_kb = 0
    for status_path in pathlib.Path("/proc").glob("[0-9]*/status"):
        try:
            for line in status_path.read_text().splitlines():
                if line.startswith("VmRSS:"):
                    total_kb += int(line.split()[1])
                    break
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    return total_kb * 1024


def run_sampler(stage, metrics_path, sample_path, interval):
    stopping = False

    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    disk_peak = 0
    memory_peak = 0
    rss_peak = 0
    samples = 0
    while True:
        disk_peak = max(disk_peak, shutil.disk_usage(sample_path).used)
        memory_peak = max(memory_peak, memory_used_bytes())
        rss_peak = max(rss_peak, process_rss_bytes())
        samples += 1
        if stopping:
            break
        time.sleep(interval)
    record_peaks(
        metrics_path,
        stage,
        disk_used_bytes=disk_peak,
        memory_used_bytes=memory_peak,
        process_rss_bytes=rss_peak,
        samples=samples,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--metrics-file", required=True)
    parser.add_argument("--path", default=".")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    run_sampler(
        args.stage,
        args.metrics_file,
        args.path,
        max(args.interval, 0.1),
    )


if __name__ == "__main__":
    main()
