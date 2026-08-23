#!/usr/bin/env python3
"""Plan and dispatch the curated large-genome benchmark campaign."""

import argparse
import csv
import json
import pathlib
import sys


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from normalize_package_name import build_package_name


def publication_action(provider, accession, existing_packages):
    """Return whether a build should publish a package to the public index."""
    exact_match = any(
        package.get("provider", "").casefold() == provider.casefold()
        and package.get("accession") == accession
        for package in existing_packages
    )
    return "skip-existing" if exact_match else "publish"


def load_manifest(path):
    """Load the checked-in benchmark definition."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def build_dispatch_payload(campaign, genome, publication, run_token=""):
    """Build the repository_dispatch client payload for one campaign row."""
    package_name, reason = build_package_name(
        genome["organism"], genome["provider"], genome["assembly"]
    )
    if not package_name:
        raise ValueError(reason)

    order = int(genome["order"])
    job_id = f'{campaign["campaign_id"]}-{order:02d}'
    if run_token:
        job_id = f"{job_id}-{run_token}"
    source_url = (
        "https://www.ncbi.nlm.nih.gov/datasets/genome/"
        f'{genome["accession"]}/'
    )
    return {
        "job_id": job_id,
        "package_name": package_name,
        "organism": genome["organism"],
        "common_name": genome.get("common_name", ""),
        "genome": genome["assembly"],
        "provider": genome["provider"],
        "version": genome.get("version", "1.0.0"),
        "accession": genome["accession"],
        "extra": {
            "data_source": "ncbi",
            "fasta_source": "ncbi",
            "publish_to_index": publication == "publish",
            "benchmark_mode": True,
            "benchmark_campaign": campaign["campaign_id"],
            "benchmark_order": order,
            "metadata_snapshot_date": campaign["metadata_snapshot_date"],
            "build_sla_seconds": campaign["build_sla_seconds"],
            "release_date": genome["release_date"],
            "title": (
                f'Full genome sequences for {genome["organism"]} '
                f'(NCBI version {genome["assembly"]})'
            ),
            "source_url": source_url,
            "ncbi_assembly_stats": {
                "assembly_level": genome["assembly_level"],
                "total_sequence_length": genome["total_sequence_length"],
                "total_ungapped_length": genome["total_ungapped_length"],
                "number_of_scaffolds": genome["number_of_scaffolds"],
                "scaffold_n50": genome["scaffold_n50"],
            },
        },
    }


def plan_campaign(campaign, catalog):
    """Return the ordered campaign with a live publication decision per row."""
    existing = catalog.get("flat", []) if isinstance(catalog, dict) else catalog
    plan = []
    for genome in sorted(campaign["genomes"], key=lambda row: int(row["order"])):
        row = dict(genome)
        publication_policy = genome.get("publication_policy", "auto")
        if publication_policy not in {"auto", "never"}:
            raise ValueError(
                "unsupported publication_policy for "
                f'{genome["accession"]}: {publication_policy}'
            )
        if publication_policy == "never":
            row["publication"] = "skip-policy"
        else:
            row["publication"] = publication_action(
                genome["provider"], genome["accession"], existing
            )
        plan.append(row)
    return plan


def summarize_campaign(campaign, reports):
    """Merge per-run reports with the manifest, retaining missing results."""
    rows = []
    for genome in sorted(campaign["genomes"], key=lambda row: int(row["order"])):
        report = reports.get(genome["accession"])
        outcome = report.get("outcome", {}) if report else {}
        timings = report.get("timings_sec", {}) if report else {}
        peaks = report.get("resource_peaks", {}) if report else {}
        rows.append(
            {
                "order": int(genome["order"]),
                "organism": genome["organism"],
                "accession": genome["accession"],
                "assembly": genome["assembly"],
                "total_sequence_length": genome["total_sequence_length"],
                "number_of_scaffolds": genome["number_of_scaffolds"],
                "scaffold_n50": genome["scaffold_n50"],
                "report_available": report is not None,
                "build_complete": bool(outcome.get("build_complete", False)),
                "build_sla_exceeded": outcome.get("build_sla_exceeded"),
                "publication": outcome.get("publication", "not-recorded"),
                "workflow_complete": bool(
                    outcome.get("workflow_complete", False)
                ),
                "failure_stage": outcome.get("failure_stage"),
                "elapsed_seconds": timings.get("workflow_to_archive"),
                "peak_disk_used_bytes": peaks.get("disk_used_bytes"),
                "peak_process_rss_bytes": peaks.get("process_rss_bytes"),
            }
        )
    return rows


def format_elapsed(seconds):
    if seconds is None:
        return "—"
    minutes, remaining = divmod(int(seconds), 60)
    return f"{minutes} min {remaining:02d} s"


def write_campaign_summary(campaign, reports_dir, output_dir):
    reports = {}
    for report_path in pathlib.Path(reports_dir).rglob("build-report.json"):
        report = load_manifest(report_path)
        accession = report.get("benchmark", {}).get("accession")
        if accession:
            reports[accession] = report
    rows = summarize_campaign(campaign, reports)
    output = pathlib.Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        f'# {campaign["campaign_id"]}',
        "",
        "| Order | Organism | Accession | Size (Gbp) | Scaffolds | N50 (bp) | Build | Elapsed | Publication |",
        "|---:|---|---|---:|---:|---:|---|---:|---|",
    ]
    for row in rows:
        if not row["report_available"]:
            build = "report missing"
        elif row["build_complete"]:
            build = "success"
        else:
            build = f'failed ({row["failure_stage"] or "unknown stage"})'
        lines.append(
            "| {order} | *{organism}* | `{accession}` | {size:.2f} | "
            "{scaffolds:,} | {n50:,} | {build} | {elapsed} | {publication} |".format(
                order=row["order"],
                organism=row["organism"],
                accession=row["accession"],
                size=row["total_sequence_length"] / 1_000_000_000,
                scaffolds=row["number_of_scaffolds"],
                n50=row["scaffold_n50"],
                build=build,
                elapsed=format_elapsed(row["elapsed_seconds"]),
                publication=row["publication"],
            )
        )
    (output / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    payload_parser = subparsers.add_parser("payload")
    payload_parser.add_argument("--manifest", required=True)
    payload_parser.add_argument("--catalog", required=True)
    payload_parser.add_argument("--accession", required=True)
    payload_parser.add_argument("--run-token", default="")
    payload_parser.add_argument("--no-publish", action="store_true")
    matrix_parser = subparsers.add_parser("matrix")
    matrix_parser.add_argument("--manifest", required=True)
    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("--manifest", required=True)
    summarize_parser.add_argument("--reports-dir", required=True)
    summarize_parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    campaign = load_manifest(args.manifest)
    if args.command == "matrix":
        include = [
            {
                "order": int(row["order"]),
                "accession": row["accession"],
                "organism": row["organism"],
            }
            for row in sorted(
                campaign["genomes"], key=lambda row: int(row["order"])
            )
        ]
        print(json.dumps({"include": include}))
        return
    if args.command == "summarize":
        rows = write_campaign_summary(
            campaign, args.reports_dir, args.output_dir
        )
        print(json.dumps({"rows": len(rows), "output_dir": args.output_dir}))
        return

    catalog = load_manifest(args.catalog)
    plan = plan_campaign(campaign, catalog)
    genome = next(
        (row for row in plan if row["accession"] == args.accession), None
    )
    if genome is None:
        parser.error(f"accession not found in manifest: {args.accession}")
    payload = build_dispatch_payload(
        campaign,
        genome,
        publication="skip-existing" if args.no_publish else genome["publication"],
        run_token=args.run_token,
    )
    print(json.dumps({"event_type": "build_bsgenome", "client_payload": payload}))


if __name__ == "__main__":
    main()
