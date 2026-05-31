#!/usr/bin/env python3
"""Backfill genome release dates in packages.json from NCBI assembly summaries."""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path


def iter_summary(path: Path):
    with path.open() as handle:
        for line in handle:
            if line.startswith("#assembly_accession"):
                headers = line.lstrip("#").rstrip("\n").split("\t")
                break
        else:
            raise ValueError(f"no assembly_summary header found in {path}")
        yield from csv.DictReader(handle, fieldnames=headers, delimiter="\t")


def normalize_release_date(value: str) -> str:
    return value.strip().replace("/", "-")


def rebuild_organisms(flat: list[dict]) -> dict:
    organisms = {}
    for pkg in flat:
        org = pkg.get("organism", "Unknown") or "Unknown"
        if org not in organisms:
            organisms[org] = {
                "organism": org,
                "common_name": pkg.get("common_name", ""),
                "group": pkg.get("group", "other"),
                "taxonomy": pkg.get("taxonomy", {}),
                "builds": [],
            }
        organisms[org]["builds"].append(pkg)
        if pkg.get("group") and pkg["group"] != "other" and organisms[org].get("group") == "other":
            organisms[org]["group"] = pkg["group"]
        if pkg.get("taxonomy") and not organisms[org].get("taxonomy"):
            organisms[org]["taxonomy"] = pkg["taxonomy"]
        if pkg.get("common_name") and not organisms[org].get("common_name"):
            organisms[org]["common_name"] = pkg["common_name"]
    return {
        "organisms": sorted(organisms.values(), key=lambda o: o["organism"]),
        "flat": flat,
    }


def fetch_ncbi_release_date(accession: str) -> str:
    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/dataset_report"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    report = (data.get("reports") or [{}])[0]
    return normalize_release_date(report.get("assembly_info", {}).get("release_date", ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", required=True, type=Path)
    parser.add_argument("--refseq-summary", required=True, type=Path)
    parser.add_argument("--genbank-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--api-missing",
        action="store_true",
        help="Use NCBI Datasets API for accessions absent from current assembly summaries.",
    )
    args = parser.parse_args()

    data = json.loads(args.packages.read_text())
    flat = data.get("flat", data) if isinstance(data, dict) else data
    wanted = {pkg.get("accession") for pkg in flat if pkg.get("accession")}

    release_by_accession: dict[str, str] = {}
    for path in (args.refseq_summary, args.genbank_summary):
        for row in iter_summary(path):
            accession = row.get("assembly_accession", "")
            if accession in wanted and accession not in release_by_accession:
                release_by_accession[accession] = normalize_release_date(row.get("seq_rel_date", ""))

    if args.api_missing:
        missing = sorted(accession for accession in wanted if accession not in release_by_accession)
        for i, accession in enumerate(missing, 1):
            try:
                release_date = fetch_ncbi_release_date(accession)
            except Exception as exc:
                print(f"api_failed {accession}: {exc}")
                stats_key = "api_failed"
            else:
                if release_date:
                    release_by_accession[accession] = release_date
                    stats_key = "api_resolved"
                else:
                    stats_key = "api_no_release_date"
            print(f"api {i}/{len(missing)} {accession} {stats_key}")
            time.sleep(0.1)

    stats = Counter()
    for pkg in flat:
        old_published = pkg.get("published")
        if old_published and not pkg.get("indexed_at"):
            pkg["indexed_at"] = old_published
            stats["moved_published_to_indexed_at"] += 1

        release_date = release_by_accession.get(pkg.get("accession", ""))
        if release_date:
            if pkg.get("release_date") != release_date:
                pkg["release_date"] = release_date
                stats["set_release_date"] += 1
            if pkg.get("published") != release_date:
                pkg["published"] = release_date
                stats["corrected_legacy_published"] += 1
        else:
            if "published" in pkg:
                pkg.pop("published", None)
                stats["removed_unresolved_legacy_published"] += 1

    args.output.write_text(json.dumps(rebuild_organisms(flat), indent=2))
    for key, value in stats.most_common():
        print(f"{key}: {value}")
    print(f"matched_accessions: {sum(1 for pkg in flat if pkg.get('release_date'))}/{len(flat)}")


if __name__ == "__main__":
    main()
