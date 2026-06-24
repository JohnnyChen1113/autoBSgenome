#!/usr/bin/env python3
"""Apply one build result to gh-pages package indexes."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def load_json_arg(value: object, default: object) -> object:
    if not value:
        return default
    if isinstance(value, str):
        return json.loads(value)
    return value


def int_or_zero(value: object) -> int:
    try:
        return int(str(value))
    except Exception:
        return 0


def load_flat_packages(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "flat" in data:
        return data["flat"]
    if isinstance(data, list):
        return data
    return []


def rebuild_organisms(flat: list[dict]) -> dict:
    organisms: dict[str, dict] = {}
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
        "organisms": sorted(organisms.values(), key=lambda item: item["organism"]),
        "flat": flat,
    }


def taxonomy_for_organism(organism: str) -> tuple[dict, str, str]:
    taxonomy = {}
    group = "other"
    common_name = ""
    try:
        encoded = urllib.parse.quote(organism)
        url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{encoded}/dataset_report"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        tax = data.get("reports", [{}])[0].get("taxonomy", {})
        classification = tax.get("classification", {})
        for rank in ["domain", "kingdom", "phylum", "class", "order", "family", "genus"]:
            if rank in classification:
                taxonomy[rank] = classification[rank]["name"]
        common_name = tax.get("curator_common_name", "")

        kingdom = taxonomy.get("kingdom", "")
        phylum = taxonomy.get("phylum", "")
        if kingdom == "Metazoa" and taxonomy.get("class") == "Mammalia":
            group = "vertebrate_mammalian"
        elif kingdom == "Metazoa" and phylum == "Chordata":
            group = "vertebrate_other"
        elif kingdom == "Metazoa":
            group = "invertebrate"
        elif kingdom == "Viridiplantae" or phylum in ("Streptophyta", "Chlorophyta"):
            group = "plant"
        elif kingdom == "Fungi":
            group = "fungi"
        elif taxonomy.get("domain") == "Bacteria":
            group = "bacteria"
        elif taxonomy.get("domain") == "Archaea":
            group = "archaea"
    except Exception as exc:
        print(f"Taxonomy lookup failed: {exc}")
    return taxonomy, group, common_name


def update_queue(path: Path, package: str, accession: str, organism: str, assembly: str) -> None:
    if not path.exists():
        return
    queue = json.loads(path.read_text())
    updated = False
    for item in queue:
        same_package = package and item.get("package_name") == package
        same_accession = accession and item.get("accession") == accession
        same_organism_assembly = (
            organism
            and assembly
            and item.get("organism") == organism
            and item.get("assembly") == assembly
        )
        if (same_package or same_accession or same_organism_assembly) and item.get("status") in (
            "building",
            "pending",
        ):
            item["status"] = "done"
            updated = True
            break
    if updated:
        path.write_text(json.dumps(queue, separators=(", ", ": ")))
        print(f"Marked {package or accession or organism} as done in build-queue.json")
    else:
        print(f"No matching queue entry found for {package or accession or organism}")


def regenerate_packages_index(packages_path: Path, output_path: Path) -> None:
    flat = load_flat_packages(packages_path)
    lines = []
    for pkg in flat:
        lines.append(f"Package: {pkg['package']}")
        lines.append(f"Version: {pkg['version']}")
        lines.append("NeedsCompilation: no")
        lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-json", default=os.environ.get("PAYLOAD", ""))
    parser.add_argument("--repo", default=os.environ.get("REPO", ""))
    parser.add_argument("--packages", type=Path, default=Path("packages.json"))
    parser.add_argument("--queue", type=Path, default=Path("build-queue.json"))
    parser.add_argument("--packages-index", type=Path, default=Path("src/contrib/PACKAGES"))
    parser.add_argument("--provenance", type=Path, default=Path("provenance/builds.jsonl"))
    args = parser.parse_args()

    payload = json.loads(args.payload_json)
    storage_info = load_json_arg(payload.get("storage_info"), {})
    metrics = storage_info.get("metrics", {}) if isinstance(storage_info, dict) else {}
    provenance = storage_info.get("provenance", {}) if isinstance(storage_info, dict) else {}

    package = payload.get("package_name", "")
    version = payload.get("version", "")
    organism = payload.get("organism", "")
    assembly = payload.get("assembly", "")
    provider = payload.get("provider", "")
    accession = payload.get("accession", "")
    file_name = payload.get("file_name", "")
    file_size = int_or_zero(payload.get("file_size", 0))
    seq_ids = storage_info.get("seq_ids") or payload.get("seq_ids", "")
    seq_count = int_or_zero(payload.get("seq_count", 0))
    storage = storage_info.get("storage") or "github-release"
    external_url = storage_info.get("download_url", "")
    doi = storage_info.get("doi", "")
    incoming_source_url = (storage_info.get("source_url", "") or "").strip()
    license_name = (storage_info.get("license", "") or "").strip()
    release_date = (storage_info.get("release_date", "") or "").strip()

    taxonomy, group, common_name = taxonomy_for_organism(organism)
    indexed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if incoming_source_url:
        source_url = incoming_source_url
    elif provider == "NCBI" and accession:
        source_url = f"https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/"
    else:
        source_url = ""
    default_url = f"https://github.com/{args.repo}/releases/download/pkg-{package}/{file_name}"

    new_entry = {
        "package": package,
        "version": version,
        "organism": organism,
        "assembly": assembly,
        "provider": provider,
        "accession": accession,
        "source_url": source_url,
        "file_name": file_name,
        "size": file_size,
        "seq_ids": seq_ids.split(",") if isinstance(seq_ids, str) and seq_ids else seq_ids or [],
        "seq_count": seq_count,
        "group": group,
        "taxonomy": taxonomy,
        "common_name": common_name,
        "indexed_at": indexed_at,
        "storage": storage,
        "download_url": external_url or default_url,
    }
    if license_name:
        new_entry["license"] = license_name
    if release_date:
        new_entry["release_date"] = release_date
        new_entry["published"] = release_date
    if doi:
        new_entry["doi"] = doi
    if metrics:
        new_entry["metrics"] = metrics
    if provenance:
        provenance.setdefault("provider", provider)
        provenance.setdefault("source_url", source_url)
        provenance.setdefault("source_accession", accession)
        new_entry["provenance"] = provenance

    flat = [pkg for pkg in load_flat_packages(args.packages) if pkg.get("package") != package]
    flat.append(new_entry)
    args.packages.write_text(json.dumps(rebuild_organisms(flat), indent=2))

    args.provenance.parent.mkdir(parents=True, exist_ok=True)
    ledger_entry = {
        "schema_version": 1,
        "event": "package_index_update",
        "indexed_at": indexed_at,
        "release_date": release_date,
        "package": package,
        "version": version,
        "provider": provider,
        "accession": accession,
        "source_url": source_url,
        "download_url": new_entry["download_url"],
        "storage": storage,
        "doi": doi,
        "provenance": provenance,
    }
    with args.provenance.open("a") as handle:
        handle.write(json.dumps(ledger_entry, sort_keys=True) + "\n")

    update_queue(args.queue, package, accession, organism, assembly)
    regenerate_packages_index(args.packages, args.packages_index)


if __name__ == "__main__":
    main()
