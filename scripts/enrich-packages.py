#!/usr/bin/env python3
"""
Enrich packages.json with missing metadata from NCBI APIs.

For each package in the `flat` array:
  - If missing taxonomy or common_name: query NCBI Taxonomy API
  - If missing seq_ids or seq_count (or seq_count is 0): query NCBI Sequence Reports API
  - Recompute `group` from taxonomy
  - Rebuild the `organisms` array from flat

Usage:
  python3 enrich-packages.py packages.json > packages-enriched.json
  cat packages.json | python3 enrich-packages.py > packages-enriched.json
"""

import json
import sys
import time
import urllib.request
import urllib.parse

TAXONOMY_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{organism}/dataset_report"
SEQUENCE_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/sequence_reports"
DELAY = 0.5  # seconds between API calls


def log(msg):
    """Print to stderr."""
    print(msg, file=sys.stderr)


def fetch_taxonomy(organism):
    """Query NCBI Taxonomy API for an organism name. Returns (taxonomy_dict, common_name)."""
    encoded = urllib.parse.quote(organism)
    url = TAXONOMY_URL.format(organism=encoded)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        report = data.get("reports", [{}])[0]
        tax = report.get("taxonomy", {})
        classification = tax.get("classification", {})

        taxonomy = {}
        for rank in ["domain", "kingdom", "phylum", "class", "order", "family", "genus"]:
            if rank in classification:
                taxonomy[rank] = classification[rank]["name"]

        common_name = tax.get("curator_common_name", "") or tax.get("common_name", "")
        return taxonomy, common_name

    except Exception as e:
        log(f"  WARNING: Taxonomy fetch failed for '{organism}': {e}")
        return None, None


def fetch_sequence_ids(accession):
    """Query NCBI Sequence Reports API. Returns (seq_ids_preview, total_count)."""
    url = SEQUENCE_URL.format(accession=accession)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        reports = data.get("reports", [])
        all_ids = []
        for r in reports:
            refseq = r.get("refseq_accession") or r.get("genbank_accession", "")
            if refseq:
                all_ids.append(refseq)

        total = len(all_ids)
        # Store only first 5 as preview
        preview = all_ids[:5]
        return preview, total

    except Exception as e:
        log(f"  WARNING: Sequence fetch failed for '{accession}': {e}")
        return None, None


def compute_group(taxonomy):
    """Compute the group classification from taxonomy dict."""
    if not taxonomy:
        return "other"

    domain = taxonomy.get("domain", "")
    kingdom = taxonomy.get("kingdom", "")
    phylum = taxonomy.get("phylum", "")
    cls = taxonomy.get("class", "")

    if domain == "Bacteria":
        return "bacteria"
    if domain == "Archaea":
        return "archaea"
    if kingdom == "Fungi":
        return "fungi"
    if kingdom == "Viridiplantae" or phylum in ("Streptophyta", "Chlorophyta"):
        return "plant"
    if kingdom == "Metazoa" and cls == "Mammalia":
        return "vertebrate_mammalian"
    if kingdom == "Metazoa" and phylum == "Chordata":
        return "vertebrate_other"
    if kingdom == "Metazoa":
        return "invertebrate"

    return "other"


def rebuild_organisms(flat):
    """Rebuild the organisms array from the flat package list."""
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

        # Update organism-level fields from the richest package
        if pkg.get("common_name") and not organisms[org].get("common_name"):
            organisms[org]["common_name"] = pkg["common_name"]
        if pkg.get("group") and pkg["group"] != "other" and organisms[org].get("group") == "other":
            organisms[org]["group"] = pkg["group"]
        if pkg.get("taxonomy") and not organisms[org].get("taxonomy"):
            organisms[org]["taxonomy"] = pkg["taxonomy"]

    return sorted(organisms.values(), key=lambda o: o["organism"])


def main():
    # Read input
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    # Extract flat list
    if isinstance(data, dict) and "flat" in data:
        flat = data["flat"]
    elif isinstance(data, list):
        flat = data
    else:
        log("ERROR: Unrecognized packages.json format")
        sys.exit(1)

    log(f"Processing {len(flat)} packages...")

    stats = {
        "taxonomy_added": 0,
        "common_name_added": 0,
        "seq_ids_added": 0,
        "seq_count_added": 0,
        "group_updated": 0,
        "skipped_no_accession": 0,
        "api_errors": 0,
    }

    for pkg in flat:
        name = pkg.get("package", "?")
        organism = pkg.get("organism", "")
        accession = pkg.get("accession", "")

        needs_taxonomy = not pkg.get("taxonomy")
        needs_common_name = not pkg.get("common_name") and pkg.get("common_name") != ""
        needs_seq = not pkg.get("seq_ids") or not pkg.get("seq_count") or pkg.get("seq_count", 0) == 0

        if not needs_taxonomy and not needs_common_name and not needs_seq:
            continue

        # --- Taxonomy / common_name ---
        if (needs_taxonomy or needs_common_name) and organism:
            log(f"  [{name}] Fetching taxonomy for '{organism}'...")
            taxonomy, common_name = fetch_taxonomy(organism)
            time.sleep(DELAY)

            if taxonomy is not None:
                if needs_taxonomy:
                    pkg["taxonomy"] = taxonomy
                    stats["taxonomy_added"] += 1
                    # Recompute group from new taxonomy
                    new_group = compute_group(taxonomy)
                    if new_group != pkg.get("group", "other"):
                        log(f"    Group: {pkg.get('group', 'other')} -> {new_group}")
                        pkg["group"] = new_group
                        stats["group_updated"] += 1
                elif not pkg.get("group") or pkg.get("group") == "other":
                    # Even if taxonomy existed, recompute group if it was 'other'
                    new_group = compute_group(pkg.get("taxonomy", {}))
                    if new_group != "other":
                        pkg["group"] = new_group
                        stats["group_updated"] += 1

                if needs_common_name and common_name:
                    pkg["common_name"] = common_name
                    stats["common_name_added"] += 1
            else:
                stats["api_errors"] += 1

        elif (needs_taxonomy or needs_common_name) and not organism:
            log(f"  [{name}] No organism name, cannot fetch taxonomy")
            stats["skipped_no_accession"] += 1

        # --- Sequence IDs ---
        if needs_seq and accession:
            log(f"  [{name}] Fetching sequences for '{accession}'...")
            seq_ids, seq_count = fetch_sequence_ids(accession)
            time.sleep(DELAY)

            if seq_ids is not None:
                if not pkg.get("seq_ids"):
                    pkg["seq_ids"] = seq_ids
                    stats["seq_ids_added"] += 1
                if not pkg.get("seq_count") or pkg.get("seq_count", 0) == 0:
                    pkg["seq_count"] = seq_count
                    stats["seq_count_added"] += 1
            else:
                stats["api_errors"] += 1

        elif needs_seq and not accession:
            log(f"  [{name}] No accession, cannot fetch sequences")
            stats["skipped_no_accession"] += 1

    # Rebuild organisms from enriched flat list
    organisms = rebuild_organisms(flat)

    result = {
        "organisms": organisms,
        "flat": flat,
    }

    # Output to stdout
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")

    # Print summary to stderr
    log("")
    log("=== Enrichment Summary ===")
    log(f"  Total packages:     {len(flat)}")
    log(f"  Taxonomy added:     {stats['taxonomy_added']}")
    log(f"  Common name added:  {stats['common_name_added']}")
    log(f"  Seq IDs added:      {stats['seq_ids_added']}")
    log(f"  Seq count added:    {stats['seq_count_added']}")
    log(f"  Group updated:      {stats['group_updated']}")
    log(f"  Skipped (no data):  {stats['skipped_no_accession']}")
    log(f"  API errors:         {stats['api_errors']}")
    log(f"  Organisms total:    {len(organisms)}")


if __name__ == "__main__":
    main()
