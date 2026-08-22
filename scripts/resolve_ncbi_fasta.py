#!/usr/bin/env python3
"""Resolve an assembly accession to its official NCBI genomic FASTA."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/genomes/all"
ACCESSION_RE = re.compile(r"^(GC[AF])_([0-9]{9})\.([0-9]+)$")
MD5_RE = re.compile(r"^([0-9a-fA-F]{32})\s+[*.]?/?(.+?)\s*$")


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def fetch_text(url: str, timeout: float) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "file":
        path = Path(urllib.request.url2pathname(parsed.path))
        if path.is_dir():
            path = path / "index.html"
        return path.read_text(encoding="utf-8")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "autoBSgenome/1.0 (https://autobsgenome.org)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def links_from(url: str, timeout: float) -> list[str]:
    parser = LinkParser()
    parser.feed(fetch_text(url, timeout))
    return [urllib.parse.urljoin(url, href) for href in parser.links]


def basename(url: str) -> str:
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path).rstrip("/")
    return path.rsplit("/", 1)[-1]


def resolve(accession: str, ftp_base: str, timeout: float) -> dict:
    match = ACCESSION_RE.fullmatch(accession)
    if not match:
        raise ValueError("accession must look like GCA_012345678.1 or GCF_012345678.1")

    prefix, digits, _version = match.groups()
    parent_url = "/".join(
        [
            ftp_base.rstrip("/"),
            prefix,
            digits[0:3],
            digits[3:6],
            digits[6:9],
            "",
        ]
    )
    assembly_urls = [
        url
        for url in links_from(parent_url, timeout)
        if basename(url).startswith(f"{accession}_")
    ]
    if len(assembly_urls) != 1:
        raise ValueError(
            f"expected one FTP directory for {accession}, found {len(assembly_urls)}"
        )

    assembly_url = assembly_urls[0].rstrip("/") + "/"
    directory_name = basename(assembly_url)
    expected_fasta_name = f"{directory_name}_genomic.fna.gz"
    expected_stats_name = f"{directory_name}_assembly_stats.txt"
    files = {basename(url): url for url in links_from(assembly_url, timeout)}
    fasta_url = files.get(expected_fasta_name)
    stats_url = files.get(expected_stats_name)
    checksum_url = files.get("md5checksums.txt")
    if not fasta_url:
        raise ValueError(f"NCBI FTP directory has no {expected_fasta_name}")
    if not checksum_url:
        raise ValueError("NCBI FTP directory has no md5checksums.txt")
    if not stats_url:
        raise ValueError(f"NCBI FTP directory has no {expected_stats_name}")

    expected_md5 = ""
    for line in fetch_text(checksum_url, timeout).splitlines():
        checksum = MD5_RE.match(line)
        if checksum and checksum.group(2).rsplit("/", 1)[-1] == expected_fasta_name:
            expected_md5 = checksum.group(1).lower()
            break
    if not expected_md5:
        raise ValueError(f"md5checksums.txt has no checksum for {expected_fasta_name}")

    total_sequence_length = 0
    for line in fetch_text(stats_url, timeout).splitlines():
        fields = line.split("\t")
        if fields[:5] == ["all", "all", "all", "all", "total-length"]:
            total_sequence_length = int(fields[5])
            break
    if total_sequence_length <= 0:
        raise ValueError(f"{expected_stats_name} has no all-sequence total-length")

    return {
        "accession": accession,
        "fasta_url": fasta_url,
        "expected_md5": expected_md5,
        "checksum_url": checksum_url,
        "assembly_stats_url": stats_url,
        "total_sequence_length": total_sequence_length,
        "assembly_directory_url": assembly_url,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("accession")
    parser.add_argument("--ftp-base", default=DEFAULT_FTP_BASE)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    try:
        report = resolve(args.accession, args.ftp_base, args.timeout)
    except Exception as exc:
        print(f"ERROR: could not resolve NCBI genomic FASTA: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(report, sort_keys=True)
    print(text)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
