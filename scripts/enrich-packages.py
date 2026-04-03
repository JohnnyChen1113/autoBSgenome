#!/usr/bin/env python3
"""
Enrich packages.json with full metadata from NCBI/Ensembl APIs.
Reads the current packages.json, looks up missing organism/assembly info,
and outputs the new organism-centric format.
"""

import json
import sys
import urllib.request
import time

NCBI_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession"


def fetch_ncbi_info(accession):
    """Fetch organism info from NCBI Datasets API."""
    try:
        url = f"{NCBI_BASE}/{accession}/dataset_report"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        report = data.get("reports", [{}])[0]
        return {
            "organism": report.get("organism", {}).get("organism_name", ""),
            "common_name": report.get("organism", {}).get("common_name", ""),
            "assembly": report.get("assembly_info", {}).get("assembly_name", ""),
            "source_url": f"https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/",
        }
    except Exception as e:
        print(f"  Warning: Failed to fetch {accession}: {e}", file=sys.stderr)
        return {}


def guess_accession_from_package(pkg_name):
    """Try to find the accession from our build-queue or release notes."""
    # Known mappings from our batch
    known = {
        "BSgenome.Eromaleae.NCBI.ASM28003v2": "GCF_000280035.1",
        "BSgenome.Eintestinalis.NCBI.ASM14646v1": "GCF_000146465.1",
        "BSgenome.Ehellem.NCBI.ASM27781v3": "GCF_000277815.2",
        "BSgenome.Ocolligata.NCBI.ASM80326v1": "GCF_000803265.1",
        "BSgenome.Ecuniculi.NCBI.ASM9122v2": "GCF_000091225.2",
        "BSgenome.Ndisplodere.NCBI.ASM164239v1": "GCF_001642395.1",
        "BSgenome.Vcorneae.NCBI.VittcornV1": "GCF_000231115.1",
        "BSgenome.Nparisii.NCBI.NemaparisiiERTm1V3": "GCF_000250985.1",
        "BSgenome.Nausubeli.NCBI.Nemasp1ERTm6V2": "GCF_000738915.1",
        "BSgenome.Mdaphniae.NCBI.UGP11": "GCF_000760515.2",
        "BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308assembly01": "GCF_016861625.1",
        "BSgenome.Aluchuensis.NCBI.AkawachiiIFO4308": "GCF_016861625.1",
        "BSgenome.Sbicolor.NCBI.SorghumbicolorNCBIv3": "GCA_000003195.3",
    }
    return known.get(pkg_name, "")


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "packages.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "packages-enriched.json"

    with open(input_file) as f:
        packages = json.load(f)

    print(f"Enriching {len(packages)} packages...", file=sys.stderr)

    # Enrich each package
    enriched = []
    for pkg in packages:
        name = pkg.get("package", "")
        accession = pkg.get("accession", "") or guess_accession_from_package(name)

        if accession and (not pkg.get("organism") or pkg["organism"] == ""):
            print(f"  Fetching info for {name} ({accession})...", file=sys.stderr)
            info = fetch_ncbi_info(accession)
            pkg["organism"] = info.get("organism", pkg.get("organism", ""))
            pkg["common_name"] = info.get("common_name", "")
            pkg["assembly"] = info.get("assembly", pkg.get("assembly", ""))
            pkg["source_url"] = info.get("source_url", "")
            pkg["accession"] = accession
            time.sleep(0.5)  # Rate limit
        elif not accession:
            print(f"  No accession for {name}, skipping enrichment", file=sys.stderr)

        enriched.append(pkg)

    # Convert to organism-centric format
    organisms = {}
    for pkg in enriched:
        org = pkg.get("organism", "Unknown")
        if org not in organisms:
            organisms[org] = {
                "organism": org,
                "common_name": pkg.get("common_name", ""),
                "builds": [],
            }
        organisms[org]["builds"].append({
            "package": pkg.get("package", ""),
            "assembly": pkg.get("assembly", ""),
            "provider": pkg.get("provider", ""),
            "accession": pkg.get("accession", ""),
            "source_url": pkg.get("source_url", ""),
            "version": pkg.get("version", "1.0.0"),
            "size": pkg.get("size", 0),
            "circ_seqs": pkg.get("circ_seqs", []),
            "published": pkg.get("published", ""),
            "download_url": pkg.get("download_url", ""),
            "file_name": pkg.get("file_name", ""),
        })

    # Also keep flat list for PACKAGES index compatibility
    result = {
        "organisms": list(organisms.values()),
        "flat": enriched,
    }

    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nResult: {len(organisms)} organisms, {len(enriched)} packages", file=sys.stderr)
    for org_name, org_data in sorted(organisms.items()):
        builds = org_data["builds"]
        print(f"  {org_name}: {len(builds)} build(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
