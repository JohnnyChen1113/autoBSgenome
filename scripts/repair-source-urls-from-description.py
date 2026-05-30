#!/usr/bin/env python3
"""
Repair packages.json source_url values from package DESCRIPTION metadata.

Input 1: packages.json from gh-pages.
Input 2: a TSV scan of package DESCRIPTION fields with columns:

  package provider current_source_url description_provider description_source_url status

The script only changes entries whose current source_url is not
provider-correct and whose DESCRIPTION contains a provider-correct
source_url for the same provider. It does not guess missing URLs.

Usage:
  python3 scripts/repair-source-urls-from-description.py \
    packages.json description-scan.tsv > packages-repaired.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any


@dataclass
class DescriptionScan:
    package: str
    provider: str
    current_source_url: str
    description_provider: str
    description_source_url: str
    status: str


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def provider_url_ok(provider: str, url: str) -> bool:
    if not url:
        return False
    if provider == "Ensembl":
        return bool(
            re.search(r"(^|\.)ensembl\.org/", url, re.I)
            and re.search(r"/Info/Index/?$", url, re.I)
        )
    if provider == "NCBI":
        return bool(
            re.match(
                r"^https://www\.ncbi\.nlm\.nih\.gov/datasets/genome/GC[AF]_\d+\.\d+/?$",
                url,
                re.I,
            )
        )
    return False


def is_broken_base_ncbi(url: str) -> bool:
    return bool(
        re.match(
            r"^https://www\.ncbi\.nlm\.nih\.gov/datasets/genome/?$",
            url or "",
            re.I,
        )
    )


def read_scan(path: str) -> dict[str, DescriptionScan]:
    scans: dict[str, DescriptionScan] = {}
    with open(path, encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            raw = raw.rstrip("\n")
            if not raw:
                continue
            parts = raw.split("\t")
            if len(parts) != 6:
                raise SystemExit(
                    f"ERROR: {path}:{line_number} has {len(parts)} columns; expected 6"
                )
            scan = DescriptionScan(*parts)
            scans[scan.package] = scan
    return scans


def get_flat(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("flat"), list):
        return data["flat"]
    if isinstance(data, list):
        return data
    raise SystemExit("ERROR: unrecognized packages.json format")


def rebuild_organisms(flat: list[dict[str, Any]]) -> list[dict[str, Any]]:
    organisms: dict[str, dict[str, Any]] = {}
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
        if pkg.get("common_name") and not organisms[org].get("common_name"):
            organisms[org]["common_name"] = pkg["common_name"]
        if (
            pkg.get("group")
            and pkg["group"] != "other"
            and organisms[org].get("group") == "other"
        ):
            organisms[org]["group"] = pkg["group"]
        if pkg.get("taxonomy") and not organisms[org].get("taxonomy"):
            organisms[org]["taxonomy"] = pkg["taxonomy"]
    return sorted(organisms.values(), key=lambda o: o["organism"])


def repair(data: Any, scans: dict[str, DescriptionScan]) -> tuple[Any, dict[str, int], list[dict[str, str]]]:
    flat = get_flat(data)
    stats = {
        "total": 0,
        "already_valid": 0,
        "updated_from_description": 0,
        "description_empty_or_broken": 0,
        "description_read_failed": 0,
        "provider_conflict": 0,
        "source_url_conflict": 0,
        "missing_scan": 0,
    }
    changes: list[dict[str, str]] = []

    for build in flat:
        stats["total"] += 1
        package = str(build.get("package") or "")
        provider = str(build.get("provider") or "")
        current_source_url = str(build.get("source_url") or "")

        if provider_url_ok(provider, current_source_url):
            stats["already_valid"] += 1
            continue

        scan = scans.get(package)
        if scan is None:
            stats["missing_scan"] += 1
            continue

        if scan.status != "ok":
            stats["description_read_failed"] += 1
            continue

        description_provider = scan.description_provider
        description_source_url = scan.description_source_url

        if description_provider and description_provider != provider:
            stats["provider_conflict"] += 1
            continue

        if provider_url_ok(provider, description_source_url):
            if current_source_url != description_source_url:
                build["source_url"] = description_source_url
                stats["updated_from_description"] += 1
                changes.append(
                    {
                        "package": package,
                        "provider": provider,
                        "before": current_source_url,
                        "after": description_source_url,
                    }
                )
            else:
                stats["already_valid"] += 1
            continue

        if not description_source_url or is_broken_base_ncbi(description_source_url):
            stats["description_empty_or_broken"] += 1
        else:
            stats["source_url_conflict"] += 1

    if isinstance(data, dict):
        result = dict(data)
        result["flat"] = flat
        result["organisms"] = rebuild_organisms(flat)
        return result, stats, changes

    return flat, stats, changes


def write_changes_tsv(path: str, changes: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("package\tprovider\tbefore\tafter\n")
        for change in changes:
            handle.write(
                "\t".join(
                    [
                        change["package"],
                        change["provider"],
                        change["before"],
                        change["after"],
                    ]
                )
                + "\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packages_json")
    parser.add_argument("description_scan_tsv")
    parser.add_argument("--report-json")
    parser.add_argument("--changes-tsv")
    parser.add_argument(
        "--fail-on-conflict",
        action="store_true",
        help="Exit non-zero if DESCRIPTION provider/source conflicts are found.",
    )
    args = parser.parse_args()

    with open(args.packages_json, encoding="utf-8") as handle:
        data = json.load(handle)

    scans = read_scan(args.description_scan_tsv)
    result, stats, changes = repair(data, scans)

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")

    log("=== Source URL Repair Summary ===")
    for key, value in stats.items():
        log(f"{key}: {value}")

    if args.report_json:
        with open(args.report_json, "w", encoding="utf-8") as handle:
            json.dump({"stats": stats, "changed": len(changes)}, handle, indent=2)
            handle.write("\n")

    if args.changes_tsv:
        write_changes_tsv(args.changes_tsv, changes)

    if args.fail_on_conflict and (
        stats["provider_conflict"] or stats["source_url_conflict"]
    ):
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
