#!/usr/bin/env python3
"""
Generate a build queue from NCBI RefSeq representative genomes.

Downloads the assembly summary, filters to representative/reference genomes,
sorts by priority (vertebrates first, then by genome size ascending),
and outputs a JSON queue file.

Usage:
    python3 scripts/generate-build-queue.py [--output build-queue.json]
"""

import csv
import json
import sys
import urllib.request
from pathlib import Path

REFSEQ_SUMMARY_URL = "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/assembly_summary_refseq.txt"

# Priority order for organism groups (lower = higher priority)
GROUP_PRIORITY = {
    "vertebrate_mammalian": 1,
    "vertebrate_other": 2,
    "plant": 3,
    "invertebrate": 4,
    "fungi": 5,
    "protozoa": 6,
    "archaea": 7,
    "bacteria": 8,
}

# Existing Bioconductor BSgenome packages — skip these
BIOCONDUCTOR_ORGANISMS = {
    "Homo sapiens", "Mus musculus", "Rattus norvegicus",
    "Danio rerio", "Drosophila melanogaster", "Caenorhabditis elegans",
    "Saccharomyces cerevisiae", "Arabidopsis thaliana",
    "Bos taurus", "Canis lupus familiaris", "Gallus gallus",
    "Pan troglodytes", "Sus scrofa", "Xenopus tropicalis",
    "Apis mellifera", "Anopheles gambiae",
}


def download_summary(cache_path="/tmp/refseq_summary.txt"):
    """Download or use cached assembly summary."""
    p = Path(cache_path)
    if not p.exists() or p.stat().st_size < 1_000_000:
        print(f"Downloading assembly summary from NCBI...", file=sys.stderr)
        urllib.request.urlretrieve(REFSEQ_SUMMARY_URL, cache_path)
    else:
        print(f"Using cached summary: {cache_path}", file=sys.stderr)
    return cache_path


def parse_summary(filepath):
    """Parse the assembly summary TSV."""
    entries = []
    with open(filepath, "r") as f:
        # Skip comment lines
        for line in f:
            if line.startswith("#assembly_accession"):
                headers = line.lstrip("#").strip().split("\t")
                break
        reader = csv.DictReader(f, fieldnames=headers, delimiter="\t")
        for row in reader:
            if row.get("refseq_category") != "reference genome":
                continue
            if row.get("version_status") != "latest":
                continue
            entries.append(row)
    return entries


def make_queue(entries):
    """Convert entries to queue items, sorted by priority."""
    queue = []
    for e in entries:
        organism = e.get("organism_name", "")
        # Skip organisms that already have Bioconductor BSgenome
        if organism in BIOCONDUCTOR_ORGANISMS:
            continue

        accession = e.get("assembly_accession", "")
        group = e.get("group", "other")
        genome_size = int(e.get("genome_size", "0") or "0")
        asm_name = e.get("asm_name", "")

        # Generate package name
        parts = organism.split()
        if len(parts) >= 2:
            abbrev = parts[0][0].upper() + parts[1].lower()
        else:
            abbrev = parts[0] if parts else "Unknown"
        assembly_clean = asm_name.replace(".", "").replace(" ", "").replace("-", "").replace("_", "")
        package_name = f"BSgenome.{abbrev}.NCBI.{assembly_clean}"

        priority = GROUP_PRIORITY.get(group, 9)

        queue.append({
            "accession": accession,
            "organism": organism,
            "assembly": asm_name,
            "package_name": package_name,
            "group": group,
            "genome_size_bp": genome_size,
            "genome_size_mb": round(genome_size / 1_000_000, 1),
            "priority": priority,
            "status": "pending",
        })

    # Sort: priority first, then genome size ascending (small builds first)
    queue.sort(key=lambda x: (x["priority"], x["genome_size_bp"]))
    return queue


def main():
    output = sys.argv[1] if len(sys.argv) > 1 else "build-queue.json"

    filepath = download_summary()
    entries = parse_summary(filepath)
    print(f"Found {len(entries)} representative/reference genomes", file=sys.stderr)

    queue = make_queue(entries)
    print(f"Queue: {len(queue)} genomes (excluded {len(entries) - len(queue)} with existing Bioconductor packages)", file=sys.stderr)

    # Stats
    groups = {}
    for item in queue:
        g = item["group"]
        groups[g] = groups.get(g, 0) + 1
    print(f"\nDistribution:", file=sys.stderr)
    for g, count in sorted(groups.items(), key=lambda x: -x[1]):
        print(f"  {g}: {count}", file=sys.stderr)

    total_size_gb = sum(item["genome_size_bp"] for item in queue) / 1_000_000_000
    print(f"\nTotal genome size: {total_size_gb:.1f} GB", file=sys.stderr)
    print(f"Estimated build time at 10/hour: {len(queue) / 240:.0f} days", file=sys.stderr)

    with open(output, "w") as f:
        json.dump(queue, f, indent=2)
    print(f"\nWrote {len(queue)} entries to {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
