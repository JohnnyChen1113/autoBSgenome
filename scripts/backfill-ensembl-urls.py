#!/usr/bin/env python3
"""
Backfill missing source_url for builds whose provider == "Ensembl".

For every community build where provider=="Ensembl" and source_url is empty,
we:
  1. Construct a candidate species-page URL using kingdom + accession
     (same logic as the web UI's ensemblSubdomain + ensemblSlug helpers).
  2. HEAD-probe it (GET fallback if HEAD is rejected).
  3. If 200 -> write the URL into build.source_url.
  4. If 404 -> mark build._ensembl_status = "not_indexed" so the UI can
     stop offering an Ensembl link for cases the upstream actually
     doesn't host.

Usage:
  python3 backfill-ensembl-urls.py packages.json > packages-backfilled.json
  cat packages.json | python3 backfill-ensembl-urls.py > packages-backfilled.json

The script is idempotent. It only touches builds that match the criteria,
so re-running it is safe — already-backfilled URLs and already-marked
not_indexed builds are skipped.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKERS = 8
TIMEOUT = 12
USER_AGENT = (
    "autoBSgenome-backfill/1.0 (+https://github.com/JohnnyChen1113/autoBSgenome)"
)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


# ---- helpers that mirror the web UI logic ----------------------------------


def strip_genus_brackets(name):
    """NCBI uses [Candida] X to flag a disputed historical genus. Strip them."""
    return re.sub(r"\[([^\]]+)\]", r"\1", name or "")


def species_name(name):
    cleaned = strip_genus_brackets(name).strip()
    parts = cleaned.split()
    return " ".join(parts[:2]) if len(parts) >= 2 else cleaned


def ensembl_subdomain(group):
    """Route by taxonomic kingdom to the matching EnsemblGenomes subsite."""
    if group in ("plant", "plants"):
        return "plants.ensembl.org"
    if group == "fungi":
        return "fungi.ensembl.org"
    if group in ("invertebrate", "metazoa"):
        return "metazoa.ensembl.org"
    if group in ("protozoa", "protists"):
        return "protists.ensembl.org"
    if group in ("bacteria", "archaea"):
        return "bacteria.ensembl.org"
    return "www.ensembl.org"  # vertebrates and unknowns


def candidate_urls(species, group, accession):
    """Return URLs to try, most likely match first.

    EnsemblGenomes uses two URL conventions:
      - /_genus_species_gca_NNNNNNNNN/Info/Index for multi-assembly species
      - /Genus_species/Info/Index for canonical single-assembly species
    Vertebrates on www.ensembl.org only use the latter.
    """
    species = species.strip()
    if not species:
        return []

    subdomain = ensembl_subdomain(group)
    is_vertebrate = (group or "").startswith("vertebrate_")
    urls = []

    # Multi-assembly slug — only for non-vertebrates with a GCA accession.
    if not is_vertebrate and accession and accession.startswith("GCA_"):
        m = re.match(r"GCA_(\d+)", accession)
        if m:
            lower = species.lower().replace(" ", "_")
            urls.append(
                f"https://{subdomain}/_{lower}_gca_{m.group(1)}/Info/Index"
            )

    # Plain slug: capital Genus, lowercase species. Ensembl uses
    # /Arabidopsis_thaliana, not /Arabidopsis_Thaliana (the latter 301s).
    parts = [p for p in species.split() if p]
    if parts:
        title = parts[0].capitalize() + (
            "_" + "_".join(p.lower() for p in parts[1:]) if len(parts) > 1 else ""
        )
        urls.append(f"https://{subdomain}/{title}/Info/Index")

    return urls


# ---- network probe ---------------------------------------------------------


def probe_url(url):
    """Return HTTP status code (200, 404, etc.) or 0 on network error."""
    # Try HEAD first; some Ensembl sites reject HEAD with 405, fall back to GET.
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url,
                method=method,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            if e.code == 405 and method == "HEAD":
                continue
            return e.code
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return 0
    return 0


def resolve_build(build):
    """Return dict with status: 'ok'|'not_indexed'|'error'|'skip' + reason."""
    species = species_name(build.get("organism", ""))
    if not species:
        return {"status": "skip", "reason": "no organism name"}

    urls = candidate_urls(species, build.get("group"), build.get("accession", ""))
    if not urls:
        return {"status": "skip", "reason": "no candidate URL"}

    last_code = None
    for url in urls:
        code = probe_url(url)
        last_code = code
        if code == 200:
            return {"status": "ok", "url": url}
        # Rate-limited or upstream-down: don't conclude "not_indexed".
        if code in (429, 503, 0):
            return {"status": "error", "reason": f"http {code}", "url": url}

    # Every candidate 404'd — the species really isn't on this subdomain.
    return {"status": "not_indexed", "reason": f"http {last_code}"}


# ---- rebuild organisms (same as enrich-packages.py) ------------------------


def rebuild_organisms(flat):
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
        if pkg.get("common_name") and not organisms[org].get("common_name"):
            organisms[org]["common_name"] = pkg["common_name"]
        if (
            pkg.get("group")
            and pkg["group"] != "other"
            and organisms[org].get("group") == "other"
        ):
            organisms[org]["group"] = pkg["group"]
        if pkg.get("taxonomy") and not organisms[org].get("taxonomy"):
            organisms[org]["taxonomy"] = pkg["taxonomy"]
    return sorted(organisms.values(), key=lambda o: o["organism"])


# ---- entrypoint ------------------------------------------------------------


def main():
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    if isinstance(data, dict) and "flat" in data:
        flat = data["flat"]
    elif isinstance(data, list):
        flat = data
    else:
        log("ERROR: Unrecognized packages.json format")
        sys.exit(1)

    log(f"Loaded {len(flat)} packages.")

    # Pick targets: provider=Ensembl, no source_url, not already marked.
    targets = []
    for build in flat:
        provider = (build.get("provider") or "").lower()
        if provider != "ensembl":
            continue
        if build.get("source_url"):
            continue
        if build.get("_ensembl_status") == "not_indexed":
            continue
        targets.append(build)

    log(f"Targets needing backfill: {len(targets)}")
    if not targets:
        log("Nothing to do. Writing input unchanged.")
        organisms = rebuild_organisms(flat)
        json.dump({"organisms": organisms, "flat": flat}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return

    stats = {"backfilled": 0, "not_indexed": 0, "errors": 0, "skipped": 0}
    done = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(resolve_build, b): b for b in targets}
        for fut in as_completed(futures):
            build = futures[fut]
            try:
                result = fut.result()
            except Exception as e:
                result = {"status": "error", "reason": str(e)}

            pkg_name = build.get("package", "?")
            organism = build.get("organism", "?")

            if result["status"] == "ok":
                build["source_url"] = result["url"]
                # Remove any prior negative marker if backfill now succeeded.
                build.pop("_ensembl_status", None)
                stats["backfilled"] += 1
                log(f"  OK  [{pkg_name}] {organism} -> {result['url']}")
            elif result["status"] == "not_indexed":
                build["_ensembl_status"] = "not_indexed"
                stats["not_indexed"] += 1
                log(f"  404 [{pkg_name}] {organism} ({result['reason']})")
            elif result["status"] == "error":
                stats["errors"] += 1
                log(
                    f"  ERR [{pkg_name}] {organism} "
                    f"({result['reason']}) — left untouched"
                )
            else:  # skip
                stats["skipped"] += 1
                log(f"  SKIP [{pkg_name}] {organism} ({result['reason']})")

            done += 1
            if done % 50 == 0:
                log(f"  ... {done}/{len(targets)} probed")

    organisms = rebuild_organisms(flat)
    json.dump({"organisms": organisms, "flat": flat}, sys.stdout, indent=2)
    sys.stdout.write("\n")

    log("")
    log("=== Backfill Summary ===")
    log(f"  Targets:          {len(targets)}")
    log(f"  Backfilled (200): {stats['backfilled']}")
    log(f"  Not indexed (404):{stats['not_indexed']}")
    log(f"  Transient errors: {stats['errors']}")
    log(f"  Skipped:          {stats['skipped']}")


if __name__ == "__main__":
    main()
