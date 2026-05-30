#!/usr/bin/env python3
"""
Validate autoBSgenome packages.json metadata.

The validator is intentionally strict about provider/source_url semantics:
Ensembl packages must link to an Ensembl species page, and NCBI packages
must link to a concrete NCBI Datasets GCA/GCF genome page. It also validates
provenance metadata when present, and can require provenance for the package
currently being indexed by the update workflow.

Usage:
  python3 scripts/validate-packages-metadata.py packages.json
  python3 scripts/validate-packages-metadata.py packages.json \
    --require-provenance-package BSgenome.Example.NCBI.ASM1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


ENSEMBL_SOURCE_RE = re.compile(r"(^|\.)ensembl\.org/.+/Info/Index/?$", re.I)
NCBI_SOURCE_RE = re.compile(
    r"^https://www\.ncbi\.nlm\.nih\.gov/datasets/genome/(GC[AF]_\d+\.\d+)/?$",
    re.I,
)
BROKEN_NCBI_BASE_RE = re.compile(
    r"^https://www\.ncbi\.nlm\.nih\.gov/datasets/genome/?$", re.I
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.I)
ISO_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def get_flat(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("flat"), list):
        return data["flat"]
    if isinstance(data, list):
        return data
    raise SystemExit("ERROR: unrecognized packages.json format")


def provider_url_ok(provider: str, url: str) -> bool:
    if provider == "Ensembl":
        return bool(ENSEMBL_SOURCE_RE.search(url or ""))
    if provider == "NCBI":
        return bool(NCBI_SOURCE_RE.match(url or ""))
    return False


def validate_package(
    package: dict[str, Any],
    require_provenance: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    name = str(package.get("package") or "")
    label = name or "<missing package>"
    provider = str(package.get("provider") or "")
    source_url = str(package.get("source_url") or "")
    accession = str(package.get("accession") or "")
    download_url = str(package.get("download_url") or "")

    if not name:
        errors.append("package is missing package name")
    if provider not in {"NCBI", "Ensembl"}:
        errors.append(f"{label}: provider must be NCBI or Ensembl, got {provider!r}")

    if not source_url:
        errors.append(f"{label}: source_url is empty")
    elif BROKEN_NCBI_BASE_RE.match(source_url):
        errors.append(f"{label}: source_url is incomplete NCBI genome base URL")
    elif provider in {"NCBI", "Ensembl"} and not provider_url_ok(provider, source_url):
        errors.append(
            f"{label}: source_url {source_url!r} is not valid for provider {provider}"
        )

    if provider == "NCBI":
        match = NCBI_SOURCE_RE.match(source_url or "")
        if match:
            source_accession = match.group(1)
            if accession and accession != source_accession:
                errors.append(
                    f"{label}: accession {accession!r} does not match source_url "
                    f"accession {source_accession!r}"
                )
            if not accession:
                errors.append(f"{label}: NCBI package is missing accession")

    if provider == "Ensembl" and accession and not accession.startswith("GCA_"):
        warnings.append(
            f"{label}: Ensembl package accession {accession!r} does not start with GCA_"
        )

    if not download_url.startswith("https://"):
        errors.append(f"{label}: download_url must be an https URL")

    provenance = package.get("provenance")
    if require_provenance and not isinstance(provenance, dict):
        errors.append(f"{label}: provenance is required for newly indexed package")
        return
    if provenance is None:
        return
    if not isinstance(provenance, dict):
        errors.append(f"{label}: provenance must be an object")
        return

    if provenance.get("schema_version") != 1:
        errors.append(f"{label}: provenance.schema_version must be 1")
    if provenance.get("provider") and provenance.get("provider") != provider:
        errors.append(f"{label}: provenance.provider does not match provider")
    if provenance.get("source_url") and provenance.get("source_url") != source_url:
        errors.append(f"{label}: provenance.source_url does not match source_url")
    if (
        provenance.get("source_accession")
        and accession
        and provenance.get("source_accession") != accession
    ):
        errors.append(f"{label}: provenance.source_accession does not match accession")

    built_at = str(provenance.get("built_at") or "")
    if built_at and not ISO_UTC_RE.match(built_at):
        errors.append(f"{label}: provenance.built_at must be UTC ISO format")

    package_sha256 = str(provenance.get("package_sha256") or "")
    if package_sha256 and not SHA256_RE.match(package_sha256):
        errors.append(f"{label}: provenance.package_sha256 is not a SHA-256 hex digest")

    description_sha256 = str(provenance.get("description_sha256") or "")
    if description_sha256 and not SHA256_RE.match(description_sha256):
        errors.append(
            f"{label}: provenance.description_sha256 is not a SHA-256 hex digest"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packages_json")
    parser.add_argument(
        "--require-provenance-package",
        action="append",
        default=[],
        help="Package name that must have a provenance object.",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Treat warnings as validation failures.",
    )
    args = parser.parse_args()

    with open(args.packages_json, encoding="utf-8") as handle:
        data = json.load(handle)

    flat = get_flat(data)
    required = set(args.require_provenance_package)
    seen: set[str] = set()
    errors: list[str] = []
    warnings: list[str] = []

    for package in flat:
        name = str(package.get("package") or "")
        if name in seen:
            errors.append(f"{name}: duplicate package entry")
        if name:
            seen.add(name)
        validate_package(package, name in required, errors, warnings)

    missing_required = sorted(required - seen)
    for name in missing_required:
        errors.append(f"{name}: required provenance package not found")

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    print(
        json.dumps(
            {
                "packages": len(flat),
                "errors": len(errors),
                "warnings": len(warnings),
                "required_provenance": sorted(required),
            },
            indent=2,
        )
    )

    if errors or (warnings and args.fail_on_warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
