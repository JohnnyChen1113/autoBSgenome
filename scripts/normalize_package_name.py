#!/usr/bin/env python3
"""Construct and validate R-compatible BSgenome package names.

R package names must match ^[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]$ with no
consecutive dots. Raw organism/assembly strings from NCBI/Ensembl often
contain characters R rejects (_, -, trailing ".", non-ASCII, placeholder
tokens like "sp."). This module centralizes the cleanup so every producer
(queue generator, dispatcher, etc.) emits identical, valid names.

Usage as library:
    from normalize_package_name import build_package_name, validate

    name, reason = build_package_name(organism, provider, assembly)
    # name is None when no valid name can be constructed; reason explains why.

Usage as CLI (smoke test):
    python3 normalize_package_name.py "Dentipellis sp. KUC8613" Ensembl ASM228671v1
"""
import re
import sys
import unicodedata

R_PACKAGE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9.]*[A-Za-z0-9]$')

# Tokens that aren't real species epithets — skip them when picking the
# second component of the abbreviation. These are taxonomic placeholders.
PLACEHOLDER_EPITHETS = {"sp", "cf", "aff", "subsp", "var", "ssp", "str"}


def _strip_accents(s: str) -> str:
    """Transliterate é→e, ü→u, etc. so ASCII-only names stay readable."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )


def _alpha_only(s: str) -> str:
    return re.sub(r'[^A-Za-z]', '', _strip_accents(s))


def _pick_species_epithet(parts: list[str]) -> str:
    """Pick a species epithet for the abbreviation.

    Placeholders like "subsp.", "var.", "str." introduce the real species or a
    sub-species qualifier and should be skipped.

    "sp.", "cf.", "aff." are different — they either mean "unknown species"
    (Dentipellis sp. KUC8613) or "compared/related to" (Vibrio cf. harveyi).
    Keep them only when what follows isn't a lowercase-looking species epithet.
    """
    for i, token in enumerate(parts[1:], start=1):
        clean = _alpha_only(token).lower()
        if not clean:
            continue
        if clean in PLACEHOLDER_EPITHETS:
            # Peek ahead: if the next token looks like a real species name
            # (starts lowercase and is alphabetic), skip this placeholder.
            if i + 1 < len(parts):
                next_tok = parts[i + 1]
                if next_tok and next_tok[0].islower() and _alpha_only(next_tok):
                    continue
            # Otherwise, "sp"/"cf"/"aff" is the best epithet we have
            return clean
        return clean
    return ""


def build_abbrev(organism: str) -> str:
    """Produce the genus-initial + species-epithet abbreviation.

    Always returns ASCII, alphabetic-only — safe to embed in an R package name.
    Empty string if the organism string is unusable.
    """
    parts = organism.strip().split()
    if not parts:
        return ""
    genus_first = _alpha_only(parts[0])[:1].upper()
    if not genus_first:
        return ""
    epithet = _pick_species_epithet(parts)
    if not epithet:
        # Single-word genus-only name: use first 6 chars of genus as abbrev
        return _alpha_only(parts[0])[:6].capitalize()
    return genus_first + epithet


def sanitize_assembly(raw: str) -> str:
    """Strip characters R rejects in package name components."""
    if not raw:
        return ""
    cleaned = _strip_accents(raw)
    # Keep only alphanumerics. Dots, dashes, underscores, spaces all removed.
    return re.sub(r'[^A-Za-z0-9]', '', cleaned)


def build_package_name(organism: str, provider: str, assembly: str):
    """Construct a BSgenome package name. Returns (name, reason).

    - name is None when the inputs can't produce a valid R package name.
    - reason explains why (empty string on success).
    """
    if not organism or not provider or not assembly:
        return None, "missing organism, provider, or assembly"

    abbrev = build_abbrev(organism)
    if not abbrev:
        return None, f"cannot build abbreviation from organism {organism!r}"

    asm_clean = sanitize_assembly(assembly)
    if not asm_clean:
        return None, f"assembly {assembly!r} has no alphanumeric content"

    provider_clean = sanitize_assembly(provider)
    if not provider_clean:
        return None, f"provider {provider!r} has no alphanumeric content"

    name = f"BSgenome.{abbrev}.{provider_clean}.{asm_clean}"
    ok, vreason = validate(name)
    if not ok:
        return None, f"constructed name {name!r} failed validation: {vreason}"
    return name, ""


def validate(name: str):
    """Return (ok, reason) for a candidate R package name."""
    if not name:
        return False, "empty"
    if ".." in name:
        return False, "consecutive dots"
    if len(name) < 2:
        return False, "too short"
    if not R_PACKAGE_RE.match(name):
        return False, "contains characters outside [A-Za-z0-9.]"
    return True, ""


def main():
    if len(sys.argv) != 4:
        print("usage: normalize_package_name.py <organism> <provider> <assembly>", file=sys.stderr)
        sys.exit(2)
    organism, provider, assembly = sys.argv[1:4]
    name, reason = build_package_name(organism, provider, assembly)
    if name:
        print(name)
        sys.exit(0)
    print(f"ERROR: {reason}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
