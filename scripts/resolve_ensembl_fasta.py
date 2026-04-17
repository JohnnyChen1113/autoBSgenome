#!/usr/bin/env python3
"""Resolve the canonical FASTA download URL for an Ensembl species.

Used by .github/workflows/build-bsgenome.yml. Handles three families:
  - main Ensembl vertebrates (ftp.ensembl.org)
  - EnsemblGenomes (fungi/plants/metazoa/protists/bacteria) on ftp.ensemblgenomes.org
  - Collection-style species (e.g. fungi_ascomycota4_collection/)

Inputs come from the build queue: species_url, group, accession.
Output: the resolved URL printed to stdout, or empty string + non-zero exit on failure.

Usage:
  python3 resolve_ensembl_fasta.py <species_url> <group> [accession]
"""
import json
import os
import re
import sys
import urllib.request
import urllib.error

DIVISION_MAP = {
    "vertebrates": None,
    "fungi": "fungi",
    "plants": "plants",
    "metazoa": "metazoa",
    "protists": "protists",
    "bacteria": "bacteria",
}

USER_AGENT = "autoBSgenome/1.0 (+https://github.com/JohnnyChen1113/autoBSgenome)"
TIMEOUT = 30


def http_get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def get_main_ensembl_release():
    s, body = http_get("https://rest.ensembl.org/info/data/?content-type=application/json")
    if s == 200:
        try:
            return json.loads(body)["releases"][0]
        except Exception:
            pass
    return 115


def find_eg_release(division):
    s, body = http_get(f"http://ftp.ensemblgenomes.org/pub/{division}/")
    if s != 200:
        return None
    rels = re.findall(r'href="release-(\d+)/?"', body)
    return max(int(r) for r in rels) if rels else None


def find_toplevel(dir_url):
    s, body = http_get(dir_url)
    if s != 200:
        return None
    m = re.search(r'href="([^"]*\.dna\.toplevel\.fa\.gz)"', body)
    return m.group(1) if m else None


def name_variants(species_norm, accession):
    """Build ordered list of candidate species directory names."""
    variants = [species_norm]
    if accession:
        acc_digits = re.sub(r'[^\d]', '', accession.split('.')[0])
        acc_ver = accession.split('.')[1] if '.' in accession else '1'
        species_clean = re.sub(r'_gca[_]?\d+(?:v\d+)?$', '', species_norm, flags=re.IGNORECASE)
        parts = species_clean.split("_")
        genus_species = "_".join(parts[:2]) if len(parts) >= 2 else species_clean
        variants += [
            f"{species_clean}_gca_{acc_digits}",
            f"{species_clean}_gca{acc_digits}",
            f"{species_clean}_gca{acc_digits}v{acc_ver}",
            f"{genus_species}_gca_{acc_digits}",
            f"{genus_species}_gca{acc_digits}",
            f"{genus_species}_gca{acc_digits}v{acc_ver}",
        ]
    seen = set()
    return [n for n in variants if not (n in seen or seen.add(n))]


def scan_collections(division, release, species_norm, accession):
    """Walk *_collection/ subdirs and look for matching species directory."""
    base = f"http://ftp.ensemblgenomes.org/pub/{division}/release-{release}/fasta/"
    s, body = http_get(base)
    if s != 200:
        return None
    cols = re.findall(r'href="([^"]*_collection)/"', body)

    candidates = name_variants(species_norm, accession)
    parts = species_norm.split("_")
    genus_species = "_".join(parts[:2]) if len(parts) >= 2 else species_norm
    acc_digits = re.sub(r'[^\d]', '', accession.split('.')[0]) if accession else None

    for col in cols:
        col_url = f"{base}{col}/"
        cs, cb = http_get(col_url)
        if cs != 200:
            continue
        for cand in candidates:
            if re.search(rf'href="{re.escape(cand)}/"', cb):
                return f"{col_url}{cand}/dna/"
        if acc_digits:
            matches = re.findall(
                rf'href="({re.escape(genus_species)}[^"]*?{acc_digits}[^"]*)/"', cb
            )
            if matches:
                return f"{col_url}{matches[0]}/dna/"
    return None


def resolve(species_url, group, accession):
    species_norm = species_url.lower()
    main_release = get_main_ensembl_release()
    print(f"[resolve] species_norm={species_norm} group={group} accession={accession} main_release={main_release}", file=sys.stderr)

    if group == "vertebrates":
        for name in name_variants(species_norm, accession):
            dir_url = f"https://ftp.ensembl.org/pub/release-{main_release}/fasta/{name}/dna/"
            print(f"[resolve] vertebrate try {dir_url}", file=sys.stderr)
            f = find_toplevel(dir_url)
            if f:
                return f"{dir_url}{f}"
        return None

    division = DIVISION_MAP.get(group)
    if not division:
        print(f"[resolve] unknown group {group!r}", file=sys.stderr)
        return None

    eg_release = find_eg_release(division)
    print(f"[resolve] EG {division} release={eg_release}", file=sys.stderr)
    if not eg_release:
        return None

    for release in (eg_release, eg_release - 1) if eg_release > 1 else (eg_release,):
        for name in name_variants(species_norm, accession):
            dir_url = f"http://ftp.ensemblgenomes.org/pub/{division}/release-{release}/fasta/{name}/dna/"
            print(f"[resolve] direct try {dir_url}", file=sys.stderr)
            f = find_toplevel(dir_url)
            if f:
                return f"{dir_url}{f}"
        col_dir = scan_collections(division, release, species_norm, accession)
        if col_dir:
            print(f"[resolve] collection match {col_dir}", file=sys.stderr)
            f = find_toplevel(col_dir)
            if f:
                return f"{col_dir}{f}"
    return None


def main():
    if len(sys.argv) < 3:
        print("usage: resolve_ensembl_fasta.py <species_url> <group> [accession]", file=sys.stderr)
        sys.exit(2)
    species_url = sys.argv[1]
    group = sys.argv[2]
    accession = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    url = resolve(species_url, group, accession)
    if url:
        print(url)
        sys.exit(0)
    print(f"ERROR: could not resolve FASTA for species_url={species_url!r} group={group!r} accession={accession!r}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
