#!/usr/bin/env python3
"""Append or set a metric in /tmp/build_metrics.json. Keyed by dotted path.

Examples:
    record_metric.py timings_sec.forge 320
    record_metric.py peak_mem_mb.rcmd_build 3800
    record_metric.py peak_disk_gb.after_fasta 18.2
    record_metric.py used_long_2bit true
    record_metric.py seq_count 27157
"""
import json
import os
import sys

PATH = os.environ.get("METRICS_FILE", "/tmp/build_metrics.json")


def parse_value(raw: str):
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def main():
    if len(sys.argv) != 3:
        print("usage: record_metric.py <dotted.key> <value>", file=sys.stderr)
        sys.exit(2)
    key_path, raw_value = sys.argv[1], sys.argv[2]

    if os.path.exists(PATH):
        with open(PATH) as f:
            metrics = json.load(f)
    else:
        metrics = {}

    node = metrics
    parts = key_path.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = parse_value(raw_value)

    with open(PATH, "w") as f:
        json.dump(metrics, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
