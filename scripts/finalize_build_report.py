#!/usr/bin/env python3
"""Finalize durable build metrics after success, failure, or skipped publish."""

import argparse
import json
import os
import pathlib


def finalize_report(metrics, *, workflow_status, publication_action):
    report = json.loads(json.dumps(metrics))
    epochs = report.get("timings_epoch", {})
    started = epochs.get("workflow_started")
    archived = epochs.get("archive_completed")
    build_complete = isinstance(started, int) and isinstance(archived, int)
    if build_complete:
        elapsed = max(0, archived - started)
        report.setdefault("timings_sec", {})["workflow_to_archive"] = elapsed
    else:
        elapsed = None

    sla = int(report.get("benchmark", {}).get("build_sla_seconds", 3600))
    workflow_complete = workflow_status == "success"
    if not build_complete:
        publication = "not-reached"
    elif publication_action == "skip-existing":
        publication = "skipped-existing"
    elif workflow_complete:
        publication = "complete"
    else:
        publication = "failed"

    report["outcome"] = {
        "build_complete": build_complete,
        "build_sla_exceeded": bool(build_complete and elapsed > sla),
        "publication": publication,
        "workflow_complete": workflow_complete,
        "workflow_status": workflow_status,
        "failure_stage": None if workflow_complete else report.get("current_stage"),
    }
    report.setdefault("provenance", {}).update(
        {
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            "workflow_sha": os.environ.get("GITHUB_SHA", ""),
            "workflow_url": (
                f'{os.environ.get("GITHUB_SERVER_URL", "https://github.com")}/'
                f'{os.environ.get("GITHUB_REPOSITORY", "")}/actions/runs/'
                f'{os.environ.get("GITHUB_RUN_ID", "")}'
            ),
        }
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--workflow-status", required=True)
    parser.add_argument(
        "--publication-action", choices=("publish", "skip-existing"), required=True
    )
    args = parser.parse_args()
    metrics_path = pathlib.Path(args.metrics_file)
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    report = finalize_report(
        metrics,
        workflow_status=args.workflow_status,
        publication_action=args.publication_action,
    )
    output_path = pathlib.Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
