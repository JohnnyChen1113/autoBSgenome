#!/usr/bin/env python3
"""Detect circular assembly molecules and map them to FASTA sequence IDs.

NCBI Datasets identifies the assembled molecules in an assembly, while
Nuccore ESummary supplies the authoritative ``topology`` value for each
sequence record.  This is deliberately stricter than guessing from molecule
type: bacterial chromosomes may be circular, and plasmids/organelles are not
universally circular.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Iterable


DATASETS_REPORT_URL = (
    "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/"
    "{accession}/sequence_reports"
)
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
USER_AGENT = "AutoBSgenome/1.0 (https://autobsgenome.org)"
ASSEMBLED_LOCATIONS = {
    "chromosome",
    "mitochondrion",
    "chloroplast",
    "plasmid",
    "apicoplast",
    "kinetoplast",
}


class DetectionError(RuntimeError):
    pass


def request_json(url: str, data: bytes | None = None, attempts: int = 3) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise DetectionError(f"expected JSON object from {url}")
            return payload
        except (OSError, ValueError, urllib.error.HTTPError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise DetectionError(f"request failed after {attempts} attempts: {last_error}")


def fetch_sequence_reports(accession: str) -> list[dict]:
    reports: list[dict] = []
    page_token = ""
    while True:
        params = {"page_size": "1000"}
        if page_token:
            params["page_token"] = page_token
        url = DATASETS_REPORT_URL.format(accession=urllib.parse.quote(accession))
        payload = request_json(f"{url}?{urllib.parse.urlencode(params)}")
        reports.extend(row for row in payload.get("reports", []) if isinstance(row, dict))
        page_token = str(payload.get("next_page_token") or "")
        if not page_token:
            break
    if not reports:
        raise DetectionError(f"NCBI returned no sequence reports for {accession}")
    return reports


def is_assembled_molecule(report: dict) -> bool:
    role = str(report.get("role") or "").lower()
    location = str(report.get("assigned_molecule_location_type") or "").lower()
    return role == "assembled-molecule" or location in ASSEMBLED_LOCATIONS


def report_accessions(report: dict) -> list[str]:
    values = [
        report.get("refseq_accession"),
        report.get("genbank_accession"),
        report.get("sequence_name"),
    ]
    return list(dict.fromkeys(str(value) for value in values if value))


def fetch_topologies(accessions: Iterable[str]) -> dict[str, str]:
    requested = list(dict.fromkeys(accessions))
    topologies: dict[str, str] = {}
    for offset in range(0, len(requested), 100):
        batch = requested[offset : offset + 100]
        data = urllib.parse.urlencode(
            {
                "db": "nuccore",
                "id": ",".join(batch),
                "retmode": "json",
                "version": "2.0",
            }
        ).encode()
        payload = request_json(ESUMMARY_URL, data=data)
        result = payload.get("result") or {}
        for uid in result.get("uids", []):
            record = result.get(str(uid)) or {}
            accession = str(record.get("accessionversion") or "")
            topology = str(record.get("topology") or "").lower()
            if accession and topology:
                topologies[accession] = topology
                topologies[accession.split(".")[0]] = topology
        if offset + 100 < len(requested):
            time.sleep(0.35)
    return topologies


def fasta_ids(path: Path) -> list[str]:
    identifiers: list[str] = []
    with path.open(errors="replace") as handle:
        for line in handle:
            if line.startswith(">"):
                identifier = line[1:].strip().split(maxsplit=1)[0]
                if identifier:
                    identifiers.append(identifier)
    if not identifiers:
        raise DetectionError(f"no FASTA headers found in {path}")
    return identifiers


def topology_for_report(report: dict, topologies: dict[str, str]) -> str:
    values = {
        topologies.get(accession, "")
        or topologies.get(accession.split(".")[0], "")
        for accession in report_accessions(report)
    }
    values.discard("")
    if "circular" in values:
        return "circular"
    if "linear" in values:
        return "linear"
    return ""


def map_report_to_fasta(report: dict, identifiers: list[str], source: str) -> str | None:
    exact = set(identifiers)
    by_unversioned: dict[str, str] = {}
    ambiguous: set[str] = set()
    for identifier in identifiers:
        key = identifier.split(".")[0]
        if key in by_unversioned and by_unversioned[key] != identifier:
            ambiguous.add(key)
        else:
            by_unversioned[key] = identifier

    refseq = str(report.get("refseq_accession") or "")
    genbank = str(report.get("genbank_accession") or "")
    sequence_name = str(report.get("sequence_name") or "")
    chromosome = str(report.get("chr_name") or "")
    if source == "ensembl":
        candidates = [chromosome, sequence_name, genbank, refseq]
    elif source == "ncbi" and genbank and not refseq:
        candidates = [genbank, sequence_name, chromosome]
    else:
        candidates = [refseq, genbank, sequence_name, chromosome]

    for candidate in candidates:
        if candidate in exact:
            return candidate
        key = candidate.split(".")[0]
        if key and key not in ambiguous and key in by_unversioned:
            return by_unversioned[key]
    return None


def detect(reports: list[dict], identifiers: list[str], source: str) -> list[str]:
    assembled = [report for report in reports if is_assembled_molecule(report)]
    if not assembled:
        raise DetectionError("sequence report contains no assembled molecules")
    accessions = [value for report in assembled for value in report_accessions(report)]
    topologies = fetch_topologies(accessions)

    unresolved = [
        report for report in assembled if not topology_for_report(report, topologies)
    ]
    if unresolved:
        examples = ", ".join(
            (report_accessions(report) or ["unknown"])[0]
            for report in unresolved[:5]
        )
        raise DetectionError(
            f"Nuccore returned no topology for {len(unresolved)} assembled molecule(s): {examples}"
        )

    circular_ids: list[str] = []
    for report in assembled:
        if topology_for_report(report, topologies) != "circular":
            continue
        identifier = map_report_to_fasta(report, identifiers, source)
        if not identifier:
            label = report_accessions(report)[0] if report_accessions(report) else "unknown"
            raise DetectionError(
                f"circular molecule {label} does not match any FASTA sequence ID"
            )
        if identifier not in circular_ids:
            circular_ids.append(identifier)
    return circular_ids


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accession", required=True)
    parser.add_argument("--fasta", required=True, type=Path)
    parser.add_argument("--source", required=True, choices=("ncbi", "ensembl"))
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()

    reports = fetch_sequence_reports(args.accession)
    identifiers = fasta_ids(args.fasta)
    circular = detect(reports, identifiers, args.source)
    result = {
        "accession": args.accession,
        "source": args.source,
        "method": "ncbi-sequence-report+nuccore-topology",
        "circular_sequences": circular,
    }
    if args.report_json:
        args.report_json.write_text(json.dumps(result, indent=2) + "\n")
    print(", ".join(circular) if circular else "character(0)")


if __name__ == "__main__":
    try:
        main()
    except DetectionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
