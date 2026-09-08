#!/usr/bin/env python3
"""Resolve the canonical FASTA download URL for an Ensembl species.

Used by .github/workflows/build-bsgenome.yml. Handles three families:
  - main Ensembl vertebrates (ftp.ensembl.org)
  - EnsemblGenomes (fungi/plants/metazoa/protists/bacteria) on the EBI FTP mirror
  - Collection-style species (e.g. fungi_ascomycota4_collection/)

Inputs come from the build queue: species_url, group, accession, expected assembly.
Assembly filenames cannot distinguish accession revisions sharing the same name.
Output: the resolved URL printed to stdout, or empty string + non-zero exit on failure.

Usage:
  python3 resolve_ensembl_fasta.py <species_url> <group> [accession] [assembly]
"""
import json
import re
import sys
import urllib.request
import urllib.error
import urllib.parse

EG_DIVISIONS = {"fungi", "plants", "metazoa", "protists", "bacteria"}
EG_FTP_BASE = "https://ftp.ensemblgenomes.ebi.ac.uk/pub"

USER_AGENT = "autoBSgenome/1.0 (+https://github.com/JohnnyChen1113/autoBSgenome)"
TIMEOUT = 30


def http_get(url):
    """GET a URL. Returns (status_code, body_text). 0 on network failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[resolve] network error for {url}: {e}", file=sys.stderr)
        return 0, ""


def get_main_ensembl_release():
    """Fetch current main-Ensembl release number. Raises on REST failure."""
    s, body = http_get("https://rest.ensembl.org/info/data/?content-type=application/json")
    if s != 200:
        raise RuntimeError(f"Ensembl REST /info/data returned HTTP {s}")
    return json.loads(body)["releases"][0]


def find_eg_release(division):
    s, body = http_get(f"{EG_FTP_BASE}/{division}/")
    if s != 200:
        return None
    rels = re.findall(r'href="release-(\d+)/?"', body)
    return max(int(r) for r in rels) if rels else None


def find_toplevel(dir_url, expected_assembly=""):
    s, body = http_get(dir_url)
    if s != 200:
        return None
    names = re.findall(r'href="([^"]*\.dna\.toplevel\.fa\.gz)"', body)
    for name in names:
        if not expected_assembly or urllib.parse.unquote(name).endswith(
            f".{expected_assembly}.dna.toplevel.fa.gz"
        ):
            return name
    if names and expected_assembly:
        print(f"[resolve] no toplevel FASTA matches assembly {expected_assembly!r} in {dir_url}", file=sys.stderr)
    return None


def fetch_assembly_metadata(species):
    species = urllib.parse.quote(species.lower(), safe="")
    status, body = http_get(
        f"https://rest.ensembl.org/info/assembly/{species}?content-type=application/json"
    )
    if status != 200:
        raise ValueError(f"Ensembl assembly metadata returned HTTP {status}")
    metadata = json.loads(body)
    if not isinstance(metadata, dict):
        raise ValueError("Ensembl assembly metadata is not an object")
    return metadata


def filename_assembly(species, expected_assembly, accession):
    """Accept an Ensembl coordinate-system alias only for matching metadata."""
    if not expected_assembly:
        return expected_assembly
    try:
        metadata = fetch_assembly_metadata(species)
        if metadata.get("assembly_name") != expected_assembly:
            return expected_assembly
        if accession and metadata.get("assembly_accession") != accession:
            return expected_assembly
        alias = metadata.get("default_coord_system_version")
        return alias if isinstance(alias, str) and alias else expected_assembly
    except ValueError:
        return expected_assembly


def name_variants(species_norm, accession):
    variants = [species_norm]

    # Ensembl mouse strains and a few fish keep the strain tag concatenated:
    # mus_musculus_pwk_phj -> mus_musculus_pwkphj
    # cyprinus_carpio_german_mirror -> cyprinus_carpio_germanmirror
    parts_orig = species_norm.split("_")
    if len(parts_orig) > 2:
        variants.append(parts_orig[0] + "_" + parts_orig[1] + "_" + "".join(parts_orig[2:]))

    if accession:
        acc_digits = re.sub(r'[^\d]', '', accession.split('.')[0])
        acc_ver = accession.split('.')[1] if '.' in accession else '1'
        # Strip any _gca... / _cn.../ cultivar-code suffix so we can re-append cleanly
        species_clean = re.sub(
            r'_(?:gca|cn)[_]?\d+(?:v\d+)?(?:cm)?$',
            '',
            species_norm,
            flags=re.IGNORECASE,
        )
        parts = species_clean.split("_")
        genus_species = "_".join(parts[:2]) if len(parts) >= 2 else species_clean
        variants += [
            f"{species_clean}_gca_{acc_digits}",
            f"{species_clean}_gca{acc_digits}",
            f"{species_clean}_gca{acc_digits}v{acc_ver}",
            # "cm" suffix appears on some EnsemblPlants paths
            # (e.g. avena_longiglumis_gca910589755v1cm)
            f"{species_clean}_gca{acc_digits}v{acc_ver}cm",
            f"{genus_species}_gca_{acc_digits}",
            f"{genus_species}_gca{acc_digits}",
            f"{genus_species}_gca{acc_digits}v{acc_ver}",
            f"{genus_species}_gca{acc_digits}v{acc_ver}cm",
        ]
    seen = set()
    return [n for n in variants if not (n in seen or seen.add(n))]


def fuzzy_listing_match(parent_url, species_norm):
    """List parent_url and find a dir whose name starts with genus_species and
    contains the strain tail (parts[2:] joined without underscores) as substring.
    Used for Ensembl mouse strains where the dir name embeds an extra subspecies
    word, e.g. mus_musculus_jf1_msj -> mus_musculus_molossinusjf1msj."""
    parts = species_norm.split("_")
    if len(parts) <= 2:
        return None
    genus_species = "_".join(parts[:2])
    tail = "".join(parts[2:])
    if not tail:
        return None
    s, body = http_get(parent_url)
    if s != 200:
        return None
    pattern = rf'href="({re.escape(genus_species)}_[^"/]*{re.escape(tail)}[^"/]*)/"'
    hits = re.findall(pattern, body)
    if len(hits) == 1:
        print(f"[resolve] fuzzy listing match: {hits[0]}", file=sys.stderr)
        return hits[0]
    if len(hits) > 1:
        print(f"[resolve] fuzzy listing ambiguous ({len(hits)} hits): {hits}", file=sys.stderr)
    return None


def try_directories(base_template, names, expected_assembly=""):
    """Probe each `base_template.format(name=n)` for a toplevel FASTA. Returns full URL or None."""
    for name in names:
        dir_url = base_template.format(name=name)
        print(f"[resolve] try {dir_url}", file=sys.stderr)
        fname = find_toplevel(dir_url, expected_assembly)
        if fname:
            return f"{dir_url}{fname}"
    return None


def scan_collections(division, release, species_norm, accession, expected_assembly=""):
    """Walk *_collection/ subdirs. Returns the final FASTA URL (not just the dir) or None."""
    base = f"{EG_FTP_BASE}/{division}/release-{release}/fasta/"
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
        matched = None
        for cand in candidates:
            if re.search(rf'href="{re.escape(cand)}/"', cb):
                matched = cand
                break
        if not matched and acc_digits:
            fuzzy = re.findall(
                rf'href="({re.escape(genus_species)}[^"]*?{acc_digits}[^"]*)/"', cb
            )
            if fuzzy:
                matched = fuzzy[0]
        if matched:
            dir_url = f"{col_url}{matched}/dna/"
            print(f"[resolve] collection hit {dir_url}", file=sys.stderr)
            fname = find_toplevel(dir_url, expected_assembly)
            if fname:
                return f"{dir_url}{fname}"
    return None


def resolve(species_url, group, accession, expected_assembly=""):
    species_norm = species_url.lower()
    print(f"[resolve] species_norm={species_norm} group={group} accession={accession}", file=sys.stderr)

    names = name_variants(species_norm, accession)
    expected_filename_assembly = filename_assembly(species_norm, expected_assembly, accession)

    if group == "vertebrates":
        release = get_main_ensembl_release()
        print(f"[resolve] main Ensembl release={release}", file=sys.stderr)
        # Vertebrates only ship the latest 1-2 releases on the FTP, but strain
        # subspecies sometimes lag behind so fall back one release if needed.
        for rel in (release, release - 1):
            base = f"https://ftp.ensembl.org/pub/release-{rel}/fasta/"
            template = f"{base}{{name}}/dna/"
            url = try_directories(template, names, expected_filename_assembly)
            if url:
                return url
            fuzzy = fuzzy_listing_match(base, species_norm)
            if fuzzy:
                dir_url = f"{base}{fuzzy}/dna/"
                fname = find_toplevel(dir_url, expected_filename_assembly)
                if fname:
                    return f"{dir_url}{fname}"
        return None

    if group not in EG_DIVISIONS:
        print(f"[resolve] unknown group {group!r}", file=sys.stderr)
        return None

    eg_release = find_eg_release(group)
    print(f"[resolve] EG {group} release={eg_release}", file=sys.stderr)
    if not eg_release:
        return None

    # EnsemblGenomes occasionally drops species from the latest release after
    # a taxonomy re-shuffle; fall back one release if current misses.
    for release in (eg_release, eg_release - 1):
        template = f"{EG_FTP_BASE}/{group}/release-{release}/fasta/{{name}}/dna/"
        url = try_directories(template, names, expected_filename_assembly)
        if url:
            return url
        url = scan_collections(group, release, species_norm, accession, expected_filename_assembly)
        if url:
            return url
    return None


def main():
    if len(sys.argv) < 3:
        print("usage: resolve_ensembl_fasta.py <species_url> <group> [accession] [assembly]", file=sys.stderr)
        sys.exit(2)
    species_url = sys.argv[1]
    group = sys.argv[2]
    accession = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    expected_assembly = sys.argv[4] if len(sys.argv) > 4 else ""
    url = resolve(species_url, group, accession, expected_assembly)
    if url:
        print(url)
        sys.exit(0)
    print(f"ERROR: could not resolve matching FASTA for species_url={species_url!r} group={group!r} accession={accession!r} assembly={expected_assembly!r}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
