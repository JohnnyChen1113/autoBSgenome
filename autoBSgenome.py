#!/usr/bin/env python3
"""Interactive local builder for BSgenome packages.

AutoBSgenome 0.8 keeps the original local build workflow while adding optional
metadata prefill from official NCBI and Ensembl identifiers and pages.  It is a
standalone Python file and intentionally uses only the standard library.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, fields
from pathlib import Path


VERSION = "0.8.0"
USER_AGENT = f"AutoBSgenome/{VERSION} (+https://autobsgenome.org)"
NCBI_REPORT_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accession}/dataset_report"
NCBI_GENOMES_BASE = "https://ftp.ncbi.nlm.nih.gov/genomes/all"
ENSEMBL_REST = "https://rest.ensembl.org"
ENSEMBL_GENOMES_FTP = "https://ftp.ensemblgenomes.ebi.ac.uk/pub"
ENSEMBL_DIVISIONS = {"fungi", "plants", "metazoa", "protists", "bacteria"}
ACCESSION_RE = re.compile(r"(GC[AF]_\d{9}\.\d+)", re.IGNORECASE)
ENSEMBL_HOST_RE = re.compile(
    r"^(?:(www|plants|fungi|bacteria|protists|metazoa)\.)?ensembl\.org$",
    re.IGNORECASE,
)
R_PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]$")
PLACEHOLDER_EPITHETS = {"sp", "cf", "aff", "subsp", "var", "ssp", "str"}


class AutoBSgenomeError(RuntimeError):
    """Expected user-facing failure."""


@dataclass(frozen=True)
class SourceInput:
    kind: str
    original: str
    accession: str = ""
    species: str = ""
    group: str = ""


@dataclass
class BuildDraft:
    package_name: str = ""
    title: str = ""
    description: str = ""
    version: str = "1.0.0"
    organism: str = ""
    common_name: str = ""
    genome: str = ""
    provider: str = ""
    release_date: str = ""
    source_url: str = ""
    organism_biocview: str = ""
    BSgenomeObjname: str = ""
    accession: str = ""
    data_source: str = "manual"
    ensembl_species: str = ""
    ensembl_group: str = ""
    ensembl_assembly: str = ""

    def generated(self) -> "BuildDraft":
        if not self.package_name:
            self.package_name = build_package_name(self.organism, self.provider, self.genome)
        if not self.title and self.organism and self.provider and self.genome:
            self.title = f"Full genome sequences for {self.organism} ({self.provider} version {self.genome})"
        if not self.description and self.organism and self.provider and self.genome:
            common = f" ({self.common_name})" if self.common_name else ""
            released = f", {self.release_date}" if self.release_date else ""
            self.description = (
                f"Full genome sequences for {self.organism}{common} as provided by "
                f"{self.provider} ({self.genome}{released}) and stored in Biostrings objects."
            )
        if not self.organism_biocview and self.organism:
            self.organism_biocview = self.organism.replace(" ", "_")
        if not self.BSgenomeObjname and self.package_name:
            parts = self.package_name.split(".")
            if len(parts) == 4:
                self.BSgenomeObjname = parts[1]
        return self

    def as_dict(self) -> dict[str, str]:
        return {field.name: str(getattr(self, field.name)) for field in fields(self)}


FIELD_HELP = {
    "package_name": "Four-part package name: BSgenome.Organism.Provider.Assembly",
    "title": "Short package title",
    "description": "One-paragraph package description",
    "version": "Package version, normally 1.0.0",
    "organism": "Scientific organism name",
    "common_name": "Common name (optional)",
    "genome": "Assembly name",
    "provider": "Sequence provider",
    "release_date": "Upstream genome assembly release date; never the package build date",
    "source_url": "Official assembly landing page (optional)",
    "organism_biocview": "Bioconductor organism term, normally with underscores (optional)",
    "BSgenomeObjname": "BSgenome object name; normally package-name part 2",
}

WIZARD_FIELDS = list(FIELD_HELP)
OPTIONAL_WIZARD_FIELDS = {"common_name", "source_url", "organism_biocview"}


def request_json(
    url: str,
    *,
    data: bytes | None = None,
    attempts: int = 3,
    timeout: int = 45,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise AutoBSgenomeError(f"Expected a JSON object from {url}")
            return payload
        except (OSError, ValueError, urllib.error.HTTPError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise AutoBSgenomeError(f"Request failed after {attempts} attempts: {last_error}")


def request_text(url: str, *, attempts: int = 3, timeout: int = 45) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except (OSError, urllib.error.HTTPError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise AutoBSgenomeError(f"Request failed after {attempts} attempts: {last_error}")


def download_file(url: str, destination: Path, *, attempts: int = 3) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            partial.replace(destination)
            return destination
        except (OSError, urllib.error.HTTPError) as error:
            last_error = error
            partial.unlink(missing_ok=True)
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise AutoBSgenomeError(f"Download failed after {attempts} attempts: {last_error}")


def clean_organism_name(value: str) -> str:
    value = re.sub(r"\[([^]]+)]", r"\1", value)
    value = re.sub(r"['\"‘’“”]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _strip_accents(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def _alpha_only(value: str) -> str:
    return re.sub(r"[^A-Za-z]", "", _strip_accents(value))


def organism_abbreviation(organism: str) -> str:
    parts = clean_organism_name(organism).split()
    if not parts:
        return ""
    genus = _alpha_only(parts[0])
    if not genus:
        return ""
    epithet = ""
    for index, token in enumerate(parts[1:], start=1):
        candidate = _alpha_only(token).lower()
        if not candidate:
            continue
        if candidate in PLACEHOLDER_EPITHETS and index + 1 < len(parts):
            following = parts[index + 1]
            if following[:1].islower() and _alpha_only(following):
                continue
        epithet = candidate
        break
    return genus[0].upper() + epithet if epithet else genus[:6].capitalize()


def sanitize_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", _strip_accents(value))


def build_package_name(organism: str, provider: str, assembly: str) -> str:
    abbreviation = organism_abbreviation(organism)
    provider_token = sanitize_component(provider)
    assembly_token = sanitize_component(assembly)
    if not abbreviation or not provider_token or not assembly_token:
        return ""
    name = f"BSgenome.{abbreviation}.{provider_token}.{assembly_token}"
    return name if R_PACKAGE_RE.fullmatch(name) and ".." not in name else ""


def validate_package_name(name: str) -> str:
    parts = name.split(".")
    if len(parts) != 4 or parts[0] != "BSgenome":
        return "Package name must have exactly four dot-separated parts and start with BSgenome."
    if not R_PACKAGE_RE.fullmatch(name) or ".." in name:
        return "Package name may contain only letters, numbers, and dots."
    return ""


def format_release_date(value: str) -> str:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", value or "")
    if not match:
        return (value or "").strip()
    months = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."]
    return f"{months[int(match.group(2)) - 1]} {match.group(1)}"


def detect_source(value: str) -> SourceInput | None:
    raw = value.strip()
    accession = ACCESSION_RE.search(raw)
    if accession and (
        not raw.lower().startswith(("http://", "https://"))
        or (urllib.parse.urlparse(raw).hostname or "").lower().endswith("ncbi.nlm.nih.gov")
    ):
        return SourceInput("ncbi", raw, accession=accession.group(1).upper())
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return None
    host_match = ENSEMBL_HOST_RE.fullmatch((parsed.hostname or "").lower())
    if not host_match:
        return None
    path_parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if not path_parts:
        return None
    group = (host_match.group(1) or "vertebrates").lower()
    if group == "www":
        group = "vertebrates"
    return SourceInput("ensembl", raw, species=path_parts[0].lower(), group=group)


def resolve_ncbi(source: SourceInput) -> BuildDraft:
    payload = request_json(NCBI_REPORT_URL.format(accession=urllib.parse.quote(source.accession)))
    reports = payload.get("reports") or []
    if not reports:
        raise AutoBSgenomeError(f"NCBI returned no assembly for {source.accession}")
    report = reports[0]
    organism_info = report.get("organism") or {}
    assembly_info = report.get("assembly_info") or {}
    draft = BuildDraft(
        organism=clean_organism_name(str(organism_info.get("organism_name") or "")),
        common_name=str(organism_info.get("common_name") or ""),
        genome=str(assembly_info.get("assembly_name") or source.accession),
        provider="NCBI",
        release_date=format_release_date(str(assembly_info.get("release_date") or "")),
        source_url=f"https://www.ncbi.nlm.nih.gov/datasets/genome/{source.accession}/",
        accession=source.accession,
        data_source="ncbi",
    )
    return draft.generated()


def fetch_ncbi_release_date(accession: str) -> str:
    """Fetch only the NCBI assembly date without the heavier sequence report."""
    payload = request_json(NCBI_REPORT_URL.format(accession=urllib.parse.quote(accession)))
    reports = payload.get("reports") or []
    if not reports:
        return ""
    assembly_info = reports[0].get("assembly_info") or {}
    return format_release_date(str(assembly_info.get("release_date") or ""))


def _fallback_organism(species: str) -> str:
    parts = species.split("_")
    return f"{parts[0].capitalize()} {parts[1]}" if len(parts) >= 2 else species.replace("_", " ").capitalize()


def resolve_ensembl(source: SourceInput) -> BuildDraft:
    species = urllib.parse.quote(source.species)
    assembly = request_json(
        f"{ENSEMBL_REST}/info/assembly/{species}?content-type=application/json",
        attempts=2,
        timeout=20,
    )
    accession = str(assembly.get("assembly_accession") or "")
    genome_info: dict = {}
    if accession:
        try:
            genome_info = request_json(
                f"{ENSEMBL_REST}/info/genomes/{urllib.parse.quote(accession)}?content-type=application/json",
                attempts=1,
                timeout=10,
            )
        except AutoBSgenomeError:
            pass
    organism = clean_organism_name(str(genome_info.get("scientific_name") or "")) or _fallback_organism(source.species)
    release_date = format_release_date(str(assembly.get("assembly_date") or ""))
    if not release_date and ACCESSION_RE.fullmatch(accession):
        try:
            release_date = fetch_ncbi_release_date(accession.upper())
        except AutoBSgenomeError:
            pass
    draft = BuildDraft(
        organism=organism,
        common_name=str(genome_info.get("display_name") or genome_info.get("common_name") or ""),
        genome=str(assembly.get("assembly_name") or accession or source.species),
        provider="Ensembl",
        release_date=release_date,
        source_url=source.original,
        accession=accession,
        data_source="ensembl",
        ensembl_species=source.species,
        ensembl_group=source.group,
        ensembl_assembly=str(
            assembly.get("default_coord_system_version") or assembly.get("assembly_name") or ""
        ),
    )
    return draft.generated()


def resolve_metadata(value: str) -> BuildDraft:
    source = detect_source(value)
    if not source:
        raise AutoBSgenomeError(
            "Automatic entry supports only NCBI accessions/URLs and official Ensembl URLs."
        )
    return resolve_ncbi(source) if source.kind == "ncbi" else resolve_ensembl(source)


def prompt_value(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{label}{suffix}: ").strip()


def confirm(question: str, default: bool = True) -> bool:
    marker = "Y/n" if default else "y/N"
    answer = input(f"{question} [{marker}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def run_wizard(draft: BuildDraft) -> BuildDraft:
    print("\nReview package metadata. Press Enter to accept a prefilled value; type 'back' to return.\n")
    index = 0
    while index < len(WIZARD_FIELDS):
        key = WIZARD_FIELDS[index]
        current = str(getattr(draft, key))
        print(f"({index + 1}/{len(WIZARD_FIELDS)}) {FIELD_HELP[key]}")
        entered = prompt_value(key, current)
        if entered.lower() == "back":
            index = max(0, index - 1)
            print()
            continue
        value = entered if entered else current
        if key not in OPTIONAL_WIZARD_FIELDS and not value.strip():
            print(f"Error: {key} is required.\n")
            continue
        if key == "package_name":
            error = validate_package_name(value)
            if error:
                print(f"Error: {error}\n")
                continue
        setattr(draft, key, value)
        index += 1
        print()
    return draft


def _name_variants(species: str, accession: str) -> list[str]:
    variants = [species]
    parts = species.split("_")
    if len(parts) > 2:
        variants.append(parts[0] + "_" + parts[1] + "_" + "".join(parts[2:]))
    if accession:
        digits = re.sub(r"\D", "", accession.split(".")[0])
        version = accession.split(".")[1] if "." in accession else "1"
        clean = re.sub(r"_(?:gca|cn)_?\d+(?:v\d+)?(?:cm)?$", "", species, flags=re.IGNORECASE)
        genus_species = "_".join(clean.split("_")[:2])
        variants.extend(
            f"{base}{suffix}"
            for base in (clean, genus_species)
            for suffix in (
                f"_gca_{digits}",
                f"_gca{digits}",
                f"_gca{digits}v{version}",
                f"_gca{digits}v{version}cm",
            )
        )
    return list(dict.fromkeys(variant for variant in variants if variant))


def _find_toplevel(directory_url: str, expected_assembly: str = "") -> str:
    try:
        listing = request_text(directory_url)
    except AutoBSgenomeError:
        return ""
    for href in re.findall(r'href="([^"]*\.dna\.toplevel\.fa\.gz)"', listing):
        filename = urllib.parse.unquote(urllib.parse.urlparse(href).path.rsplit("/", 1)[-1])
        if expected_assembly and not filename.endswith(f".{expected_assembly}.dna.toplevel.fa.gz"):
            continue
        return urllib.parse.urljoin(directory_url, href)
    return ""


def _latest_ensembl_release(group: str) -> int:
    if group == "vertebrates":
        payload = request_json(f"{ENSEMBL_REST}/info/data/?content-type=application/json")
        releases = payload.get("releases") or []
        if not releases:
            raise AutoBSgenomeError("Ensembl returned no current release")
        return int(releases[0])
    listing = request_text(f"{ENSEMBL_GENOMES_FTP}/{group}/")
    releases = [int(value) for value in re.findall(r'href="release-(\d+)/?"', listing)]
    if not releases:
        raise AutoBSgenomeError(f"No Ensembl {group} release found")
    return max(releases)


def resolve_ensembl_fasta(
    species: str, group: str, accession: str, *, expected_assembly: str = ""
) -> str:
    release = _latest_ensembl_release(group)
    names = _name_variants(species.lower(), accession)
    for candidate_release in (release, release - 1):
        if group == "vertebrates":
            base = f"https://ftp.ensembl.org/pub/release-{candidate_release}/fasta/"
        elif group in ENSEMBL_DIVISIONS:
            base = f"{ENSEMBL_GENOMES_FTP}/{group}/release-{candidate_release}/fasta/"
        else:
            raise AutoBSgenomeError(f"Unsupported Ensembl division: {group}")
        for name in names:
            resolved = _find_toplevel(f"{base}{name}/dna/", expected_assembly)
            if resolved:
                return resolved
        if group in ENSEMBL_DIVISIONS:
            try:
                listing = request_text(base)
            except AutoBSgenomeError:
                continue
            collections = re.findall(r'href="([^"]*_collection)/"', listing)
            for collection in collections:
                collection_url = f"{base}{collection}/"
                try:
                    collection_listing = request_text(collection_url)
                except AutoBSgenomeError:
                    continue
                for name in names:
                    if re.search(rf'href="{re.escape(name)}/"', collection_listing):
                        resolved = _find_toplevel(f"{collection_url}{name}/dna/", expected_assembly)
                        if resolved:
                            return resolved
    assembly_detail = f" matching assembly {expected_assembly}" if expected_assembly else ""
    raise AutoBSgenomeError(f"Could not resolve an official Ensembl FASTA for {species}{assembly_detail}")


def _copy_or_decompress(source: Path, destination: Path) -> Path:
    if not source.is_file():
        raise AutoBSgenomeError(f"FASTA file does not exist: {source}")
    partial: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, prefix=f".{destination.name}-", suffix=".part", delete=False
        ) as output:
            partial = Path(output.name)
            if source.name.lower().endswith(".gz"):
                with gzip.open(source, "rb") as compressed:
                    shutil.copyfileobj(compressed, output)
            else:
                with source.open("rb") as original:
                    shutil.copyfileobj(original, output)
        partial.replace(destination)
    except (OSError, EOFError, zlib.error) as error:
        if partial is not None:
            partial.unlink(missing_ok=True)
        raise AutoBSgenomeError(f"Could not read FASTA file {source}: {error}") from error
    return destination


def _ncbi_accession_directory(accession: str) -> str:
    match = ACCESSION_RE.fullmatch(accession.upper())
    if not match:
        raise AutoBSgenomeError(f"Invalid NCBI assembly accession: {accession}")
    normalized = match.group(1).upper()
    prefix, versioned_digits = normalized.split("_", 1)
    digits = versioned_digits.split(".", 1)[0]
    groups = "/".join(digits[index : index + 3] for index in range(0, 9, 3))
    return f"{NCBI_GENOMES_BASE}/{prefix}/{groups}/"


def resolve_ncbi_fasta_url(accession: str) -> tuple[str, str]:
    """Resolve the assembly genomic FASTA and checksum URL from NCBI HTTPS."""
    normalized = accession.upper()
    parent = _ncbi_accession_directory(normalized)
    listing = request_text(parent)
    directories = re.findall(
        rf'href="({re.escape(normalized)}_[^"/]+/)"',
        listing,
        flags=re.IGNORECASE,
    )
    if not directories:
        raise AutoBSgenomeError(f"NCBI FTP directory not found for {normalized}")
    assembly_directory = urllib.parse.urljoin(parent, directories[0])
    directory_name = directories[0].rstrip("/")
    expected_name = f"{directory_name}_genomic.fna.gz"
    assembly_listing = request_text(assembly_directory)
    hrefs = re.findall(r'href="([^"]+\.fna\.gz)"', assembly_listing, flags=re.IGNORECASE)
    filename = next((name for name in hrefs if name == expected_name), "")
    if not filename:
        filename = next(
            (
                name
                for name in hrefs
                if name.endswith("_genomic.fna.gz")
                and "_cds_from_genomic" not in name
                and "_rna_from_genomic" not in name
            ),
            "",
        )
    if not filename:
        raise AutoBSgenomeError(f"NCBI genomic FASTA not found for {normalized}")
    return (
        urllib.parse.urljoin(assembly_directory, filename),
        urllib.parse.urljoin(assembly_directory, "md5checksums.txt"),
    )


def _expected_ncbi_md5(checksum_url: str, filename: str) -> str:
    checksums = request_text(checksum_url)
    match = re.search(
        rf"^([0-9a-fA-F]{{32}})\s+\./{re.escape(filename)}$",
        checksums,
        flags=re.MULTILINE,
    )
    return match.group(1).lower() if match else ""


def _file_md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_ensembl_sum(checksum_url: str, filename: str) -> tuple[int, int] | None:
    try:
        checksums = request_text(checksum_url, attempts=1, timeout=20)
    except AutoBSgenomeError:
        return None
    for line in checksums.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) != 3 or parts[2].removeprefix("./") != filename:
            continue
        try:
            checksum, blocks = int(parts[0]), int(parts[1])
        except ValueError as error:
            raise AutoBSgenomeError(f"Invalid Ensembl checksum entry for {filename}") from error
        if not 0 <= checksum <= 65535 or blocks < 0:
            raise AutoBSgenomeError(f"Invalid Ensembl checksum entry for {filename}")
        return checksum, blocks
    return None


def _file_bsd_sum(path: Path) -> tuple[int, int]:
    checksum = 0
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            # Ensembl CHECKSUMS uses BSD sum: rotate 16 bits, then add each byte.
            for value in chunk:
                checksum = ((checksum >> 1) + ((checksum & 1) << 15) + value) & 65535
    return checksum, (size + 1023) // 1024


def download_ncbi_fasta(accession: str, workspace: Path) -> Path:
    fasta_url, checksum_url = resolve_ncbi_fasta_url(accession)
    filename = urllib.parse.unquote(urllib.parse.urlparse(fasta_url).path.rsplit("/", 1)[-1])
    print(f"Downloading {fasta_url}")
    compressed = download_file(fasta_url, workspace / "genome.fa.gz")
    expected_md5 = _expected_ncbi_md5(checksum_url, filename)
    if expected_md5:
        actual_md5 = _file_md5(compressed)
        if actual_md5 != expected_md5:
            raise AutoBSgenomeError(
                f"NCBI FASTA checksum mismatch: expected {expected_md5}, got {actual_md5}"
            )
    else:
        print("Warning: NCBI checksum entry was not found; continuing without MD5 verification.")
    destination = _copy_or_decompress(compressed, workspace / "genome.fa")
    compressed.unlink(missing_ok=True)
    return destination


def download_ensembl_fasta(draft: BuildDraft, workspace: Path) -> Path:
    if not draft.ensembl_assembly:
        raise AutoBSgenomeError("Ensembl did not provide the assembly name needed to verify the official FASTA")
    url = resolve_ensembl_fasta(
        draft.ensembl_species,
        draft.ensembl_group,
        draft.accession,
        expected_assembly=draft.ensembl_assembly,
    )
    print(f"Downloading {url}")
    compressed = download_file(url, workspace / "genome.fa.gz")
    filename = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit("/", 1)[-1])
    expected_sum = _expected_ensembl_sum(urllib.parse.urljoin(url, "CHECKSUMS"), filename)
    if expected_sum is not None:
        actual_sum = _file_bsd_sum(compressed)
        if actual_sum != expected_sum:
            raise AutoBSgenomeError(
                f"Ensembl FASTA checksum mismatch: expected {expected_sum}, got {actual_sum}"
            )
    else:
        print("Warning: Ensembl checksum entry was unavailable; continuing without checksum verification.")
    destination = _copy_or_decompress(compressed, workspace / "genome.fa")
    compressed.unlink(missing_ok=True)
    return destination


def choose_fasta(draft: BuildDraft, workspace: Path) -> Path:
    official_available = draft.data_source in {"ncbi", "ensembl"}
    if official_available:
        print("\nFASTA source")
        print("  1. Download the official FASTA")
        print("  2. Use a local FASTA file")
        choice = prompt_value("Choose", "1") or "1"
    else:
        choice = "2"
    if choice == "1":
        try:
            if draft.data_source == "ncbi":
                return download_ncbi_fasta(draft.accession, workspace)
            return download_ensembl_fasta(draft, workspace)
        except AutoBSgenomeError as error:
            print(f"Official FASTA download is unavailable: {error}")
            if not confirm("Use a local FASTA file instead", True):
                raise
    while True:
        entered = prompt_value("Local FASTA path")
        path = Path(entered).expanduser().resolve()
        try:
            return _copy_or_decompress(path, workspace / "genome.fa")
        except AutoBSgenomeError as error:
            print(f"Error: {error}")


def _dcf_value(value: str) -> str:
    return re.sub(r"[\r\n]+", " ", str(value)).strip()


def write_seed(draft: BuildDraft, workspace: Path) -> Path:
    seed = workspace / f"{draft.package_name}.seed"
    values = {
        "Package": draft.package_name,
        "Title": draft.title,
        "Description": draft.description,
        "Version": draft.version,
        "organism": draft.organism,
        "common_name": draft.common_name,
        "genome": draft.genome,
        "provider": draft.provider,
        "release_date": draft.release_date,
        "source_url": draft.source_url,
        "organism_biocview": draft.organism_biocview,
        "BSgenomeObjname": draft.BSgenomeObjname,
        "circ_seqs": "character(0)",
        "seqs_srcdir": str(workspace),
        "seqfile_name": "genome.2bit",
    }
    seed.write_text("\n".join(f"{key}: {_dcf_value(value)}" for key, value in values.items()) + "\n")
    return seed


def _run_r_script(code: str, workspace: Path, *arguments: Path) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".R", encoding="utf-8") as script:
        script.write(code)
        script.flush()
        subprocess.run(
            ["Rscript", "--vanilla", script.name, *(str(argument) for argument in arguments)],
            cwd=workspace, check=True,
        )


def prepare_forge_seed(seed: Path, workspace: Path) -> Path:
    """Keep literal metadata tokens out of upstream recursive template expansion."""
    forge_seed = seed.with_name(seed.stem + ".forge.seed")
    code = '''
    args <- commandArgs(TRUE)
    metadata <- read.dcf(args[1])
    fields <- intersect(colnames(metadata), c("Title", "Description", "organism",
        "common_name", "genome", "provider", "release_date", "source_url", "organism_biocview"))
    for (name in fields)
        metadata[1L, name] <- gsub("@", "[at]", metadata[1L, name], fixed=TRUE)
    write.dcf(metadata, args[2], keep.white=colnames(metadata))
    '''
    _run_r_script(code, workspace, seed, forge_seed)
    return forge_seed


def rewrite_forged_metadata(seed: Path, workspace: Path) -> None:
    """Rebuild executable R and Rd files using literals from the original DCF data."""
    code = r'''
    seed_path <- normalizePath(commandArgs(trailingOnly=TRUE)[1], mustWork=TRUE)
    seed <- read.dcf(seed_path)[1L, ]
    field <- function(data, name) {
        if (!name %in% names(data) || is.na(data[[name]])) return("")
        data[[name]]
    }
    package <- field(seed, "Package")
    if (!grepl("^[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]$", package) ||
        grepl("..", package, fixed=TRUE)) stop("Invalid package name")
    package_dir <- file.path(dirname(seed_path), package)
    template_dir <- system.file("pkgtemplates", "BSgenome_datapkg",
                                package="BSgenomeForge", mustWork=TRUE)
    rd_template <- system.file("pkgtemplates", "2bit_BSgenome_datapkg", "man", "package.Rd",
                               package="BSgenomeForge", mustWork=TRUE)
    output_r <- file.path(package_dir, "R", "zzz.R")
    output_rd <- file.path(package_dir, "man", "package.Rd")
    if (!file.exists(output_r) || !file.exists(output_rd))
        stop("BSgenomeForge did not create the expected R and Rd files")
    description_path <- file.path(package_dir, "DESCRIPTION")
    description <- read.dcf(description_path)[1L, ]
    description_changed <- FALSE
    metadata_fields <- c("Title", "Description", "organism", "common_name", "genome",
                         "provider", "release_date", "source_url")
    for (name in intersect(metadata_fields, names(seed))) {
        value <- field(seed, name)
        if (!identical(value, field(description, name))) {
            description[[name]] <- value
            description_changed <- TRUE
        }
    }
    biocviews <- paste0("AnnotationData, Genetics, BSgenome, ", field(seed, "organism_biocview"))
    if (!identical(biocviews, field(description, "biocViews"))) {
        description[["biocViews"]] <- biocviews
        description_changed <- TRUE
    }

    # Match only the original trusted template so inserted placeholder-like text
    # cannot be processed as another substitution.
    substitute <- function(path, values, pattern) {
        text <- paste(readLines(path, warn=FALSE, encoding="UTF-8"), collapse="\n")
        locations <- gregexpr(pattern, text, perl=TRUE)
        tokens <- regmatches(text, locations)[[1L]]
        if (any(!tokens %in% names(values)))
            stop("Unknown placeholder in BSgenomeForge template")
        regmatches(text, locations) <- list(unname(values[tokens]))
        text
    }
    r_fields <- c(PKGNAME="Package", ORGANISM="organism", COMMONNAME="common_name",
                  GENOME="genome", PROVIDER="provider", RELEASEDATE="release_date",
                  SOURCEURL="source_url", BSGENOMEOBJNAME="BSgenomeObjname")
    r_values <- vapply(r_fields, function(name) {
        encodeString(field(seed, name), quote='"')
    }, character(1))
    names(r_values) <- paste0('"@', names(r_fields), '@"')
    r_values <- c(r_values, "@SEQNAMES@"="NULL", "@CIRCSEQS@"="character(0)",
                  "@MSEQNAMES@"="NULL")
    r_text <- substitute(file.path(template_dir, "R", "zzz.R"), r_values,
                         '"@[A-Z]+@"|@[A-Z]+@')

    escape_rd <- function(value) {
        chars <- strsplit(value, "", fixed=TRUE)[[1L]]
        special <- chars %in% c("\\", "{", "}", "%")
        chars[special] <- paste0("\\", chars[special])
        paste0(chars, collapse="")
    }
    rd_values <- c(PKGNAME=package, BSGENOMEOBJNAME=field(seed, "BSgenomeObjname"),
                   PKGTITLE=field(description, "Title"),
                   PKGDESCRIPTION=field(description, "Description"),
                   PKGAUTHOR=field(description, "Author"),
                   FORGEFUN="forgeBSgenomeDataPkg")
    rd_values <- vapply(rd_values, escape_rd, character(1))
    names(rd_values) <- paste0("@", names(rd_values), "@")
    rd_text <- substitute(rd_template, rd_values, "@[A-Z]+@")
    writeLines(r_text, output_r, useBytes=TRUE)
    writeLines(rd_text, output_rd, useBytes=TRUE)
    if (description_changed)
        write.dcf(as.data.frame(as.list(description), check.names=FALSE),
                  description_path, keep.white=c(metadata_fields, "biocViews"))
    '''
    _run_r_script(code, workspace, seed)


def check_local_dependencies() -> tuple[str, str]:
    rscript = shutil.which("Rscript")
    r = shutil.which("R")
    converter = shutil.which("faToTwoBit")
    missing = [name for name, path in (("Rscript", rscript), ("R", r), ("faToTwoBit", converter)) if not path]
    if missing:
        raise AutoBSgenomeError("Missing required command(s): " + ", ".join(missing))
    subprocess.run(
        [
            rscript,
            "--vanilla",
            "-e",
            "p <- c('BSgenome','BSgenomeForge'); m <- p[!vapply(p, requireNamespace, logical(1), quietly=TRUE)]; if(length(m)) stop(paste(m, collapse=', '))",
        ],
        check=True,
    )
    return str(r), str(converter)


def build_package(draft: BuildDraft, fasta: Path, workspace: Path, *, install: bool) -> Path:
    r, converter = check_local_dependencies()
    size = fasta.stat().st_size
    command = [converter]
    if size > 12 * 1024 * 1024 * 1024:
        command.append("-long")
    command.extend([str(fasta), str(workspace / "genome.2bit")])
    subprocess.run(command, check=True)

    seed = write_seed(draft, workspace)
    print("\nSeed file:\n")
    print(seed.read_text())
    forge_seed = prepare_forge_seed(seed, workspace)
    forge_code = (
        "suppressPackageStartupMessages(library(BSgenome)); "
        "BSgenomeForge::forgeBSgenomeDataPkg(commandArgs(trailingOnly=TRUE)[1])"
    )
    subprocess.run(["Rscript", "--vanilla", "-e", forge_code, str(forge_seed)], cwd=workspace, check=True)
    package_dir = workspace / draft.package_name
    if not package_dir.is_dir():
        raise AutoBSgenomeError("BSgenomeForge did not create the expected package directory")
    rewrite_forged_metadata(seed, workspace)
    environment = os.environ.copy()
    environment["R_BUILD_TAR"] = shutil.which("tar") or "tar"
    if sys.platform == "darwin":
        environment["R_BUILD_TAR"] = shlex.quote(environment["R_BUILD_TAR"]) + " --no-xattrs"
    environment["R_PROFILE"] = os.devnull
    environment["R_PROFILE_USER"] = os.devnull
    # macOS tar metadata can contain binary xattrs that R's untar cannot read.
    environment["COPYFILE_DISABLE"] = "1"
    subprocess.run(
        [r, "CMD", "build", "--no-manual", "--no-build-vignettes", draft.package_name],
        cwd=workspace,
        env=environment,
        check=True,
    )
    tarballs = sorted(workspace.glob(f"{draft.package_name}_*.tar.gz"))
    if not tarballs:
        raise AutoBSgenomeError("R CMD build completed without producing a tarball")
    destination = Path.cwd() / tarballs[-1].name
    shutil.copy2(tarballs[-1], destination)
    if install:
        subprocess.run([r, "CMD", "INSTALL", str(destination)], env=environment, check=True)
    return destination


def print_draft(draft: BuildDraft) -> None:
    print("\nFinal metadata")
    print("-" * 72)
    for key in WIZARD_FIELDS:
        print(f"{key}: {getattr(draft, key)}")
    print("-" * 72)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a BSgenome package locally with optional NCBI/Ensembl metadata prefill."
    )
    parser.add_argument("source", nargs="?", help="NCBI accession/URL or official Ensembl species URL")
    parser.add_argument("--manual", action="store_true", help="Skip source lookup and enter all metadata manually")
    parser.add_argument("--no-install", action="store_true", help="Build the package tarball without installing it")
    parser.add_argument("--version", action="version", version=f"autoBSgenome {VERSION}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"AutoBSgenome {VERSION} — local BSgenome builder")
    draft = BuildDraft()
    source_value = "" if args.manual else (args.source or prompt_value("NCBI accession/URL or Ensembl URL (blank for manual entry)"))
    if source_value:
        try:
            print("Fetching official metadata...")
            draft = resolve_metadata(source_value)
            print(f"Metadata loaded from {draft.provider}.")
        except AutoBSgenomeError as error:
            print(f"Metadata lookup failed: {error}")
            if source_value.startswith(("http://", "https://")):
                draft.source_url = source_value
            if not confirm("Continue with manual entry", True):
                return 1
    draft = run_wizard(draft)
    print_draft(draft)
    if not confirm("Continue to FASTA selection and local build", True):
        print("Cancelled.")
        return 0

    try:
        with tempfile.TemporaryDirectory(prefix="autobsgenome-") as temporary:
            workspace = Path(temporary)
            # Fail before a potentially large download when the local build
            # toolchain is incomplete.
            check_local_dependencies()
            fasta = choose_fasta(draft, workspace)
            install = not args.no_install and confirm("Install the package after building", True)
            tarball = build_package(draft, fasta, workspace, install=install)
        print(f"\nBuild complete: {tarball}")
        return 0
    except (AutoBSgenomeError, subprocess.CalledProcessError, OSError) as error:
        print(f"\nBuild failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
