#!/usr/bin/env python3
"""Update build-queue.json with current NCBI reference genome coverage.

This is a queue maintenance script, not a build step. It expects NCBI
assembly_summary TSV files and an existing build-queue.json, then:

- marks stale Ensembl resolver failures as skip_unresolved_ensembl;
- restores all queued archaea from skip_prokaryote to pending;
- restores/adds a small bacterial pilot set from RefSeq reference genomes;
- adds a representative set of missing current reference eukaryotes from RefSeq.

GenBank reference genomes are intentionally not queued wholesale. The GenBank
reference set is large enough to swamp the catalog, so those assemblies should
be handled through smaller representative selections or on-demand builds.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from normalize_package_name import build_package_name


REFSEQ_EUKARYOTE_LIMITS = {
    "vertebrate_mammalian": 80,
    "vertebrate_other": 120,
    "plant": 80,
    "invertebrate": 120,
    "fungi": 100,
    "protozoa": 20,
}

ASSEMBLY_LEVEL_RANK = {
    "Complete Genome": 0,
    "Chromosome": 1,
    "Scaffold": 2,
    "Contig": 3,
}

BACTERIA_PRIORITY_PATTERNS = [
    r"\bEscherichia coli\b",
    r"\bBacillus subtilis\b",
    r"\bStaphylococcus aureus\b",
    r"\bStreptococcus pneumoniae\b",
    r"\bStreptococcus pyogenes\b",
    r"\bSalmonella enterica\b",
    r"\bPseudomonas aeruginosa\b",
    r"\bMycobacterium tuberculosis\b",
    r"\bVibrio cholerae\b",
    r"\bHelicobacter pylori\b",
    r"\bListeria monocytogenes\b",
    r"\bKlebsiella pneumoniae\b",
    r"\bAcinetobacter baumannii\b",
    r"\bNeisseria gonorrhoeae\b",
    r"\bNeisseria meningitidis\b",
    r"\bCampylobacter jejuni\b",
    r"\bClostridioides difficile\b",
    r"\bCorynebacterium diphtheriae\b",
    r"\bCaulobacter vibrioides\b",
    r"\bDeinococcus radiodurans\b",
    r"\bThermus thermophilus\b",
    r"\bSynechocystis\b",
    r"\bStreptomyces coelicolor\b",
    r"\bLactobacillus acidophilus\b",
    r"\bBifidobacterium longum\b",
]


def iter_summary(path: Path) -> Iterable[dict[str, str]]:
    with path.open() as handle:
        for line in handle:
            if line.startswith("#assembly_accession"):
                headers = line.lstrip("#").rstrip("\n").split("\t")
                break
        else:
            raise ValueError(f"no assembly_summary header found in {path}")
        yield from csv.DictReader(handle, fieldnames=headers, delimiter="\t")


def clean_organism(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_release_date(value: str) -> str:
    return value.strip().replace("/", "-")


def queue_item(row: dict[str, str], status: str = "pending") -> dict[str, object] | None:
    organism = clean_organism(row.get("organism_name", ""))
    assembly = row.get("asm_name", "").strip()
    accession = row.get("assembly_accession", "").strip()
    group = row.get("group", "other").strip() or "other"
    genome_size = int(row.get("genome_size", "0") or "0")
    release_date = normalize_release_date(row.get("seq_rel_date", ""))
    package_name, reason = build_package_name(organism, "NCBI", assembly)
    if not package_name:
        return {
            "accession": accession,
            "organism": organism,
            "assembly": assembly,
            "package_name": "",
            "group": group,
            "genome_size_bp": genome_size,
            "genome_size_mb": round(genome_size / 1_000_000, 1),
            "priority": 9,
            "status": "skip_malformed",
            "release_date": release_date,
            "skip_reason": reason,
        }
    item = {
        "accession": accession,
        "organism": organism,
        "assembly": assembly,
        "package_name": package_name,
        "group": group,
        "genome_size_bp": genome_size,
        "genome_size_mb": round(genome_size / 1_000_000, 1),
        "priority": priority_for_group(group),
        "status": status,
    }
    if release_date:
        item["release_date"] = release_date
    return item


def priority_for_group(group: str) -> int:
    return {
        "vertebrate_mammalian": 1,
        "vertebrate_other": 2,
        "plant": 3,
        "invertebrate": 4,
        "fungi": 5,
        "protozoa": 6,
        "archaea": 7,
        "bacteria": 8,
    }.get(group, 9)


def dedupe_key(item: dict[str, object]) -> str:
    package_name = str(item.get("package_name") or "")
    if package_name:
        return f"pkg:{package_name}"
    accession = str(item.get("accession") or "")
    return f"acc:{accession}"


def bacteria_priority(row: dict[str, str]) -> tuple[int, int, int, str]:
    organism = clean_organism(row.get("organism_name", ""))
    for i, pattern in enumerate(BACTERIA_PRIORITY_PATTERNS):
        if re.search(pattern, organism, flags=re.I):
            return (0, i, ASSEMBLY_LEVEL_RANK.get(row.get("assembly_level", ""), 9), organism)
    return (
        1,
        ASSEMBLY_LEVEL_RANK.get(row.get("assembly_level", ""), 9),
        int(row.get("genome_size", "0") or "0"),
        organism,
    )


def select_bacteria(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    candidates = [
        row
        for row in rows
        if row.get("version_status") == "latest"
        and row.get("refseq_category") == "reference genome"
        and row.get("group") == "bacteria"
        and row.get("assembly_level") in {"Complete Genome", "Chromosome"}
    ]
    candidates.sort(key=bacteria_priority)

    selected: list[dict[str, str]] = []
    seen_accessions: set[str] = set()
    seen_genera: set[str] = set()

    for row in candidates:
        organism = clean_organism(row.get("organism_name", ""))
        accession = row.get("assembly_accession", "")
        if accession in seen_accessions:
            continue
        if any(re.search(pattern, organism, flags=re.I) for pattern in BACTERIA_PRIORITY_PATTERNS):
            selected.append(row)
            seen_accessions.add(accession)
            seen_genera.add(organism.split()[0])
            if len(selected) >= limit:
                return selected

    for row in candidates:
        organism = clean_organism(row.get("organism_name", ""))
        accession = row.get("assembly_accession", "")
        genus = organism.split()[0] if organism else ""
        if accession in seen_accessions or genus in seen_genera:
            continue
        selected.append(row)
        seen_accessions.add(accession)
        seen_genera.add(genus)
        if len(selected) >= limit:
            return selected

    for row in candidates:
        accession = row.get("assembly_accession", "")
        if accession in seen_accessions:
            continue
        selected.append(row)
        seen_accessions.add(accession)
        if len(selected) >= limit:
            break
    return selected


def eukaryote_priority(row: dict[str, str]) -> tuple[int, int, str]:
    return (
        ASSEMBLY_LEVEL_RANK.get(row.get("assembly_level", ""), 9),
        int(row.get("genome_size", "0") or "0"),
        clean_organism(row.get("organism_name", "")),
    )


def select_refseq_eukaryotes(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_group: dict[str, list[dict[str, str]]] = {group: [] for group in REFSEQ_EUKARYOTE_LIMITS}
    for row in rows:
        group = row.get("group")
        if row.get("version_status") != "latest":
            continue
        if row.get("refseq_category") != "reference genome":
            continue
        if group not in by_group:
            continue
        by_group[group].append(row)

    selected: list[dict[str, str]] = []
    for group, group_rows in by_group.items():
        limit = REFSEQ_EUKARYOTE_LIMITS[group]
        group_rows.sort(key=eukaryote_priority)
        group_selected: list[dict[str, str]] = []
        seen_accessions: set[str] = set()
        seen_genera: set[str] = set()

        for row in group_rows:
            organism = clean_organism(row.get("organism_name", ""))
            genus = organism.split()[0] if organism else ""
            accession = row.get("assembly_accession", "")
            if accession in seen_accessions or genus in seen_genera:
                continue
            group_selected.append(row)
            seen_accessions.add(accession)
            seen_genera.add(genus)
            if len(group_selected) >= limit:
                break

        if len(group_selected) < limit:
            for row in group_rows:
                accession = row.get("assembly_accession", "")
                if accession in seen_accessions:
                    continue
                group_selected.append(row)
                seen_accessions.add(accession)
                if len(group_selected) >= limit:
                    break

        selected.extend(group_selected)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--packages", required=True, type=Path)
    parser.add_argument("--refseq-summary", required=True, type=Path)
    parser.add_argument("--genbank-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bacteria-limit", type=int, default=200)
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text())
    packages_data = json.loads(args.packages.read_text())
    packages = packages_data.get("flat", packages_data) if isinstance(packages_data, dict) else packages_data
    published_packages = {item.get("package") for item in packages}
    published_accessions = {item.get("accession") for item in packages if item.get("provider") == "NCBI"}

    refseq_rows = list(iter_summary(args.refseq_summary))
    wanted_accessions = {
        str(item.get("accession")) for item in queue if item.get("accession")
    }
    release_by_accession = {}
    for row in refseq_rows:
        accession = row.get("assembly_accession", "")
        if accession in wanted_accessions:
            release_by_accession[accession] = normalize_release_date(row.get("seq_rel_date", ""))
    for row in iter_summary(args.genbank_summary):
        accession = row.get("assembly_accession", "")
        if accession in wanted_accessions and accession not in release_by_accession:
            release_by_accession[accession] = normalize_release_date(row.get("seq_rel_date", ""))

    by_key = {dedupe_key(item): item for item in queue}
    by_accession = {str(item.get("accession")): item for item in queue if item.get("accession")}
    by_package = {
        str(item.get("package_name")): item for item in queue if item.get("package_name")
    }

    changes = Counter()

    for item in queue:
        accession = str(item.get("accession") or "")
        release_date = release_by_accession.get(accession)
        if release_date and item.get("release_date") != release_date:
            item["release_date"] = release_date
            changes["set_existing_release_date"] += 1

    for item in queue:
        if item.get("status") != "building":
            continue
        if item.get("package_name") in published_packages:
            item["status"] = "done"
            changes["building_to_done"] += 1
        elif item.get("data_source") == "ensembl":
            item["status"] = "skip_unresolved_ensembl"
            item["skip_reason"] = "Ensembl FASTA resolver could not locate this assembly."
            changes["building_to_skip_unresolved_ensembl"] += 1

    for item in queue:
        if item.get("group") == "archaea" and item.get("status") == "skip_prokaryote":
            item["status"] = "pending"
            item.pop("skip_reason", None)
            changes["restored_archaea"] += 1

    for row in select_bacteria(refseq_rows, args.bacteria_limit):
        accession = row.get("assembly_accession")
        if accession in published_accessions:
            continue
        if accession in by_accession:
            item = by_accession[accession]
            if item.get("status") == "skip_prokaryote":
                item["status"] = "pending"
                item.pop("skip_reason", None)
                changes["restored_bacteria"] += 1
            continue
        item = queue_item(row)
        if item:
            package_name = str(item.get("package_name") or "")
            if package_name in published_packages or package_name in by_package:
                continue
            queue.append(item)
            by_key[dedupe_key(item)] = item
            by_accession[str(item.get("accession"))] = item
            by_package[package_name] = item
            changes["added_bacteria"] += 1

    for row in select_refseq_eukaryotes(refseq_rows):
        accession = row.get("assembly_accession")
        if accession in published_accessions or accession in by_accession:
            continue
        item = queue_item(row)
        if not item:
            continue
        package_name = str(item.get("package_name") or "")
        if package_name in published_packages or package_name in by_package:
            continue
        item["queue_source"] = "ncbi_refseq_reference_2026-05-31"
        queue.append(item)
        by_key[dedupe_key(item)] = item
        by_accession[str(item.get("accession"))] = item
        by_package[package_name] = item
        changes["added_refseq_eukaryote"] += 1

    queue.sort(
        key=lambda item: (
            str(item.get("status") or ""),
            int(item.get("priority") or 9),
            int(item.get("genome_size_bp") or 0),
            str(item.get("package_name") or ""),
        )
    )

    args.output.write_text(json.dumps(queue, separators=(", ", ": ")))
    print("changes")
    for key, value in changes.most_common():
        print(f"  {key}: {value}")
    print("status")
    for key, value in Counter(str(item.get("status")) for item in queue).most_common():
        print(f"  {key}: {value}")
    print("groups")
    for key, value in Counter(str(item.get("group")) for item in queue).most_common():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
