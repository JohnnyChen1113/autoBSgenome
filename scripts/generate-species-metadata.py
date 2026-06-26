#!/usr/bin/env python3
"""Generate sharded species metadata for the package browser.

The public package browser intentionally keeps `catalog.json` compact. This
script builds a richer, optional metadata layer that the frontend can load by
letter shard when a user is browsing a subset of organisms.

Inputs are the gh-pages package indexes plus optional NCBI assembly summary
files and an incremental NCBI Taxonomy cache. The script is deterministic when
network enrichment is disabled, and can be run repeatedly with a fetch limit to
fill taxonomy fields over time.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TAXONOMY_URL = "https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{taxon}/dataset_report"
RANKS = ("domain", "kingdom", "phylum", "class", "order", "family", "genus")
IMAGE_HOST = "https://www.ensembl.org/i/species"


def log(message: str) -> None:
    print(message, file=sys.stderr)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(f"{text}\n", encoding="utf-8")


def strip_genus_brackets(name: str) -> str:
    return re.sub(r"\[([^\]]+)\]", r"\1", name)


def clean_name(value: str) -> str:
    return re.sub(r"\s+", " ", strip_genus_brackets(value or "")).strip()


def species_name(value: str) -> str:
    parts = clean_name(value).split()
    return " ".join(parts[:2]) if len(parts) >= 2 else clean_name(value)


def lookup_key(value: str) -> str:
    return clean_name(value).lower()


COMMON_IMAGE_SPECIES = (
    "Homo sapiens",
    "Mus musculus",
    "Rattus norvegicus",
    "Danio rerio",
    "Drosophila melanogaster",
    "Caenorhabditis elegans",
    "Arabidopsis thaliana",
    "Saccharomyces cerevisiae",
    "Schizosaccharomyces pombe",
    "Oryza sativa",
    "Zea mays",
    "Triticum aestivum",
    "Glycine max",
    "Solanum lycopersicum",
    "Solanum tuberosum",
    "Vitis vinifera",
    "Hordeum vulgare",
    "Sorghum bicolor",
    "Brassica rapa",
    "Brachypodium distachyon",
    "Populus trichocarpa",
    "Gossypium hirsutum",
    "Medicago truncatula",
    "Bos taurus",
    "Sus scrofa",
    "Gallus gallus",
    "Canis lupus",
    "Felis catus",
    "Macaca mulatta",
    "Pan troglodytes",
    "Gorilla gorilla",
    "Ovis aries",
    "Capra hircus",
    "Equus caballus",
    "Oryctolagus cuniculus",
    "Xenopus tropicalis",
    "Xenopus laevis",
    "Takifugu rubripes",
    "Oryzias latipes",
    "Gasterosteus aculeatus",
    "Anopheles gambiae",
    "Aedes aegypti",
    "Apis mellifera",
    "Tribolium castaneum",
    "Bombyx mori",
    "Ciona intestinalis",
    "Candida albicans",
    "Neurospora crassa",
    "Aspergillus nidulans",
    "Cryptococcus neoformans",
    "Escherichia coli",
    "Bacillus subtilis",
    "Staphylococcus aureus",
    "Pseudomonas aeruginosa",
)
COMMON_IMAGE_PRIORITY = {
    lookup_key(name): index for index, name in enumerate(COMMON_IMAGE_SPECIES)
}


def shard_key(value: str) -> str:
    first = species_name(value)[:1].upper()
    return first if "A" <= first <= "Z" else "_"


def image_slug(value: str) -> str:
    parts = species_name(value).split()
    if len(parts) < 2:
        return ""
    cleaned = []
    for index, part in enumerate(parts[:2]):
        token = re.sub(r"[^A-Za-z0-9]+", "_", part).strip("_")
        if not token:
            return ""
        if index == 0:
            cleaned.append(token[:1].upper() + token[1:].lower())
        else:
            cleaned.append(token.lower())
    return "_".join(cleaned)


def image_candidate(value: str, group: str) -> str:
    if group in {"bacteria", "archaea", "viral"}:
        return ""
    slug = image_slug(value)
    return f"{IMAGE_HOST}/{slug}.png" if slug else ""


def image_probe_priority(entry: dict[str, Any]) -> tuple[int, int, int, int, str]:
    name = str(entry.get("scientific_name") or entry.get("canonical_name") or entry["organism"])
    key = lookup_key(species_name(name))
    common_rank = COMMON_IMAGE_PRIORITY.get(key, len(COMMON_IMAGE_PRIORITY) + 1000)
    built_rank = 0 if entry.get("has_build") else 1
    group = str(entry.get("group") or "")
    image_friendly_group_rank = 0 if group in {
        "vertebrate_mammalian",
        "vertebrate_other",
        "invertebrate",
        "metazoa",
        "plant",
        "plants",
        "fungi",
    } else 1
    common_name_rank = 0 if entry.get("common_name") else 1
    return (common_rank, built_rank, image_friendly_group_rank, common_name_rank, key)


def cached_image_path(image_dir: Path, entry: dict[str, Any], candidate_url: str) -> Path:
    slug = image_slug(entry.get("scientific_name") or entry.get("canonical_name") or entry["organism"])
    if not slug:
        slug = image_slug(Path(urllib.parse.urlparse(candidate_url).path).stem)
    taxid = entry.get("species_taxid") or entry.get("taxid")
    stem = f"{slug}-{taxid}" if taxid else slug
    shard = shard_key(slug or entry["organism"])
    return image_dir / shard / f"{stem}.png"


def image_public_url(image_base_url: str, image_dir: Path, path: Path) -> str:
    rel = path.relative_to(image_dir).as_posix()
    return f"{image_base_url.rstrip('/')}/{rel}"


def load_packages(path: Path) -> list[dict[str, Any]]:
    data = load_json(path, [])
    if isinstance(data, dict):
        return list(data.get("flat") or [])
    if isinstance(data, list):
        return data
    raise SystemExit(f"ERROR: unrecognized packages format in {path}")


def load_catalog(path: Path) -> list[dict[str, Any]]:
    data = load_json(path, [])
    if not isinstance(data, list):
        raise SystemExit(f"ERROR: unrecognized catalog format in {path}")
    return data


def load_assembly_summaries(paths: list[Path]) -> dict[str, dict[str, str]]:
    by_accession: dict[str, dict[str, str]] = {}
    for path in paths:
        if not path.exists():
            log(f"WARNING: assembly summary not found: {path}")
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#assembly_accession"):
                    headers = line.lstrip("#").rstrip("\n").split("\t")
                    break
            else:
                raise SystemExit(f"ERROR: no assembly_summary header found in {path}")

            for row in csv.DictReader(handle, fieldnames=headers, delimiter="\t"):
                accession = row.get("assembly_accession", "").strip()
                if not accession:
                    continue
                by_accession[accession] = {
                    "accession": accession,
                    "taxid": row.get("taxid", "").strip(),
                    "species_taxid": row.get("species_taxid", "").strip(),
                    "organism": clean_name(row.get("organism_name", "")),
                    "assembly_level": row.get("assembly_level", "").strip(),
                    "release_date": row.get("seq_rel_date", "").strip().replace("/", "-"),
                }
    return by_accession


def taxonomy_from_report(report: dict[str, Any]) -> dict[str, Any]:
    tax = report.get("taxonomy") or {}
    classification = tax.get("classification") or {}
    taxonomy: dict[str, str] = {}
    for rank in RANKS:
        value = classification.get(rank)
        if isinstance(value, dict) and value.get("name"):
            taxonomy[rank] = str(value["name"])

    current = tax.get("current_scientific_name") or {}
    scientific_name = current.get("name") or tax.get("organism_name") or ""
    common_name = tax.get("curator_common_name") or tax.get("common_name") or ""
    return {
        "taxid": tax.get("tax_id"),
        "rank": tax.get("rank") or "",
        "scientific_name": scientific_name,
        "canonical_name": species_name(str(scientific_name or "")),
        "common_name": common_name,
        "taxonomy": taxonomy,
    }


def fetch_taxonomy(taxon: str, delay: float) -> dict[str, Any] | None:
    url = TAXONOMY_URL.format(taxon=urllib.parse.quote(str(taxon)))
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read())
        reports = data.get("reports") or []
        if not reports:
            return None
        return taxonomy_from_report(reports[0])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        log(f"WARNING: taxonomy fetch failed for {taxon!r}: {exc}")
        return None
    finally:
        if delay > 0:
            time.sleep(delay)


def probe_image(url: str, timeout: float = 2.0) -> bool:
    if not url:
        return False
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            return 200 <= response.status < 300 and content_type.startswith("image/")
    except Exception:
        return False


def download_image(url: str, path: Path, max_bytes: int, timeout: float = 10.0) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"Accept": "image/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return False

            tmp_path = path.with_suffix(path.suffix + ".tmp")
            total = 0
            with tmp_path.open("wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        tmp_path.unlink(missing_ok=True)
                        return False
                    handle.write(chunk)
            tmp_path.replace(path)
            return True
    except Exception:
        return False


def merge_taxonomy(existing: dict[str, str], incoming: dict[str, str]) -> dict[str, str]:
    merged = dict(incoming or {})
    merged.update(existing or {})
    return {key: value for key, value in merged.items() if value}


def compute_group(taxonomy: dict[str, str], fallback: str) -> str:
    if fallback and fallback != "other":
        return fallback
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
    if kingdom == "Viridiplantae" or phylum in {"Streptophyta", "Chlorophyta"}:
        return "plant"
    if kingdom == "Metazoa" and cls == "Mammalia":
        return "vertebrate_mammalian"
    if kingdom == "Metazoa" and phylum == "Chordata":
        return "vertebrate_other"
    if kingdom == "Metazoa":
        return "invertebrate"
    return fallback or "other"


def add_alias(entry: dict[str, Any], value: str) -> None:
    key = lookup_key(value)
    if key:
        entry.setdefault("_aliases", set()).add(key)


def build_entries(
    packages: list[dict[str, Any]],
    bioc_packages: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    assembly_by_accession: dict[str, dict[str, str]],
    taxonomy_cache: dict[str, dict[str, Any]],
    fetch_taxonomy_enabled: bool,
    fetch_limit: int,
    fetch_delay: float,
    probe_images: bool,
    image_probe_limit: int,
    download_images: bool,
    image_dir: Path | None,
    image_base_url: str,
    image_download_limit: int,
    max_image_bytes: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, int]]:
    entries: dict[str, dict[str, Any]] = {}
    stats = defaultdict(int)
    fetched = 0
    probed_images = 0
    downloaded_images = 0

    def ensure(organism: str) -> dict[str, Any]:
        clean = clean_name(organism) or "Unknown"
        key = lookup_key(clean)
        if key not in entries:
            entries[key] = {
                "organism": clean,
                "canonical_name": species_name(clean),
                "group": "",
                "taxonomy": {},
                "_aliases": {key},
            }
        return entries[key]

    for source_name, rows in (("community", packages), ("bioconductor", bioc_packages)):
        for package in rows:
            organism = package.get("organism") or ""
            if not organism:
                continue
            entry = ensure(str(organism))
            entry["has_build"] = True
            entry.setdefault("sources", set()).add(source_name)
            entry["group"] = entry.get("group") or package.get("group") or ""
            if package.get("common_name") and not entry.get("common_name"):
                entry["common_name"] = str(package["common_name"])
            if package.get("taxonomy"):
                entry["taxonomy"] = merge_taxonomy(entry.get("taxonomy") or {}, package["taxonomy"])
            accession = package.get("accession")
            if accession:
                entry.setdefault("accessions", set()).add(str(accession))
                summary = assembly_by_accession.get(str(accession))
                if summary:
                    if summary.get("taxid") and not entry.get("taxid"):
                        entry["taxid"] = int(summary["taxid"])
                    if summary.get("species_taxid") and not entry.get("species_taxid"):
                        entry["species_taxid"] = int(summary["species_taxid"])
                    if summary.get("assembly_level") and not entry.get("assembly_level"):
                        entry["assembly_level"] = summary["assembly_level"]
                    if summary.get("release_date") and not entry.get("release_date"):
                        entry["release_date"] = summary["release_date"]

    for row in catalog:
        organism = row.get("o") or ""
        if not organism:
            continue
        entry = ensure(str(organism))
        entry.setdefault("sources", set()).add(str(row.get("s") or "catalog"))
        entry["group"] = entry.get("group") or row.get("g") or ""
        accession = str(row.get("a") or "")
        if accession:
            entry.setdefault("accessions", set()).add(accession)
            summary = assembly_by_accession.get(accession)
            if summary:
                add_alias(entry, summary.get("organism") or "")
                if summary.get("taxid") and not entry.get("taxid"):
                    entry["taxid"] = int(summary["taxid"])
                if summary.get("species_taxid") and not entry.get("species_taxid"):
                    entry["species_taxid"] = int(summary["species_taxid"])
                if summary.get("assembly_level") and not entry.get("assembly_level"):
                    entry["assembly_level"] = summary["assembly_level"]
                if summary.get("release_date") and not entry.get("release_date"):
                    entry["release_date"] = summary["release_date"]

    for key, entry in entries.items():
        taxon = str(entry.get("species_taxid") or entry.get("taxid") or "")
        cached = taxonomy_cache.get(taxon) if taxon else None
        if not cached and fetch_taxonomy_enabled and taxon and fetched < fetch_limit:
            cached = fetch_taxonomy(taxon, fetch_delay)
            fetched += 1
            stats["taxonomy_fetch_attempted"] += 1
            if cached:
                taxonomy_cache[taxon] = cached
                stats["taxonomy_fetch_succeeded"] += 1

        if cached:
            if cached.get("scientific_name"):
                entry["scientific_name"] = clean_name(str(cached["scientific_name"]))
                add_alias(entry, entry["scientific_name"])
            if cached.get("canonical_name"):
                entry["canonical_name"] = clean_name(str(cached["canonical_name"]))
                add_alias(entry, entry["canonical_name"])
            if cached.get("common_name") and not entry.get("common_name"):
                entry["common_name"] = str(cached["common_name"])
            if cached.get("rank"):
                entry["rank"] = str(cached["rank"])
            if cached.get("taxonomy"):
                entry["taxonomy"] = merge_taxonomy(entry.get("taxonomy") or {}, cached["taxonomy"])

        entry["group"] = compute_group(entry.get("taxonomy") or {}, entry.get("group") or "")

    for entry in sorted(entries.values(), key=image_probe_priority):
        candidate = image_candidate(entry.get("scientific_name") or entry["canonical_name"], entry["group"])
        image_path = (
            cached_image_path(image_dir, entry, candidate)
            if download_images and image_dir and candidate
            else None
        )
        if image_path and image_path.exists() and image_base_url:
            entry["image_url"] = image_public_url(image_base_url, image_dir, image_path)
            stats["image_cache_hits"] += 1
            continue

        if probe_images and candidate and probed_images < image_probe_limit:
            probed_images += 1
            stats["image_probe_attempted"] += 1
            if probe_image(candidate):
                if (
                    download_images
                    and image_path
                    and image_base_url
                    and downloaded_images < image_download_limit
                ):
                    if download_image(candidate, image_path, max_image_bytes):
                        entry["image_url"] = image_public_url(image_base_url, image_dir, image_path)
                        downloaded_images += 1
                        stats["image_downloaded"] += 1
                    else:
                        entry["image_url"] = candidate
                        stats["image_download_failed"] += 1
                else:
                    entry["image_url"] = candidate
                stats["image_probe_succeeded"] += 1

    stats["taxonomy_cache_entries"] = len(taxonomy_cache)
    stats["species_entries"] = len(entries)
    return entries, taxonomy_cache, dict(stats)


def serializable_entry(entry: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "organism",
        "canonical_name",
        "scientific_name",
        "common_name",
        "group",
        "rank",
        "taxid",
        "species_taxid",
        "assembly_level",
        "release_date",
        "image_url",
    ):
        value = entry.get(key)
        if value not in (None, "", [], {}):
            result[key] = value
    taxonomy = entry.get("taxonomy") or {}
    if taxonomy:
        result["taxonomy"] = taxonomy
    sources = sorted(str(item) for item in entry.get("sources", set()) if item)
    if sources:
        result["sources"] = sources
    aliases = sorted(item for item in entry.get("_aliases", set()) if item != lookup_key(entry["organism"]))
    if aliases:
        result["aliases"] = aliases[:8]
    return result


def write_shards(entries: dict[str, dict[str, Any]], out_dir: Path, stats: dict[str, int]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        if old.name != "taxonomy-cache.json":
            old.unlink()

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    by_shard: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    unique_counts: dict[str, int] = defaultdict(int)
    for key, entry in sorted(entries.items()):
        public_entry = serializable_entry(entry)
        lookup_keys = {
            key,
            lookup_key(public_entry["organism"]),
            lookup_key(public_entry.get("canonical_name", "")),
            lookup_key(public_entry.get("scientific_name", "")),
            *(public_entry.get("aliases") or []),
        }
        for lookup in sorted(item for item in lookup_keys if item):
            shard = shard_key(lookup)
            by_shard[shard].setdefault(lookup, public_entry)
        unique_counts[shard_key(key)] += 1

    shard_summaries = []
    for key in sorted(by_shard):
        path = out_dir / f"{key}.json"
        data = {
            "version": 1,
            "generated_at": generated_at,
            "key": key,
            "entries": by_shard[key],
        }
        write_json(path, data)
        shard_summaries.append({"key": key, "path": f"{key}.json", "count": unique_counts[key]})

    index = {
        "version": 1,
        "generated_at": generated_at,
        "total": len(entries),
        "stats": stats,
        "shards": shard_summaries,
    }
    write_json(out_dir / "index.json", index)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", required=True, type=Path)
    parser.add_argument("--bioc-packages", type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--assembly-summary", action="append", type=Path, default=[])
    parser.add_argument("--taxonomy-cache", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--fetch-taxonomy", action="store_true")
    parser.add_argument("--fetch-limit", type=int, default=0)
    parser.add_argument("--fetch-delay", type=float, default=0.12)
    parser.add_argument("--probe-images", action="store_true")
    parser.add_argument("--image-probe-limit", type=int, default=0)
    parser.add_argument("--download-images", action="store_true")
    parser.add_argument("--image-dir", type=Path)
    parser.add_argument("--image-base-url", default="")
    parser.add_argument("--image-download-limit", type=int, default=0)
    parser.add_argument("--max-image-bytes", type=int, default=1_500_000)
    args = parser.parse_args()

    packages = load_packages(args.packages)
    bioc_packages = load_json(args.bioc_packages, []) if args.bioc_packages else []
    catalog = load_catalog(args.catalog)
    assembly_by_accession = load_assembly_summaries(args.assembly_summary)
    taxonomy_cache = load_json(args.taxonomy_cache, {}) if args.taxonomy_cache else {}

    entries, taxonomy_cache, stats = build_entries(
        packages=packages,
        bioc_packages=bioc_packages,
        catalog=catalog,
        assembly_by_accession=assembly_by_accession,
        taxonomy_cache=taxonomy_cache,
        fetch_taxonomy_enabled=args.fetch_taxonomy,
        fetch_limit=max(args.fetch_limit, 0),
        fetch_delay=args.fetch_delay,
        probe_images=args.probe_images,
        image_probe_limit=max(args.image_probe_limit, 0),
        download_images=args.download_images,
        image_dir=args.image_dir,
        image_base_url=args.image_base_url,
        image_download_limit=max(args.image_download_limit, 0),
        max_image_bytes=max(args.max_image_bytes, 1),
    )

    write_shards(entries, args.out_dir, stats)
    if args.taxonomy_cache:
        write_json(args.taxonomy_cache, taxonomy_cache)

    log("species metadata generated")
    for key, value in sorted(stats.items()):
        log(f"  {key}: {value}")


if __name__ == "__main__":
    main()
