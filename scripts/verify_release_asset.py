#!/usr/bin/env python3
"""Verify that a published release contains the exact locally built archive."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys


def verify_asset(assets, filename, size, sha256, download_hash):
    matches = [asset for asset in assets if asset.get("name") == filename]
    if len(matches) != 1:
        raise ValueError(f"published release must contain exactly one matching filename: {filename}")
    asset = matches[0]
    if asset.get("size") != size:
        raise ValueError("published asset size differs from the local archive")
    digest = asset.get("digest") or ""
    if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        existing_sha256 = digest.split(":", 1)[1]
    else:
        existing_sha256, downloaded_size = download_hash()
        if downloaded_size != size:
            raise ValueError("downloaded asset size differs from the local archive")
    if existing_sha256.lower() != sha256.lower():
        raise ValueError("published asset SHA-256 differs from the local archive")


def download_asset_hash(tag, filename, repo):
    command = ["gh", "release", "download", tag, "--repo", repo, "--pattern", filename, "--output", "-"]
    digest = hashlib.sha256()
    size = 0
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        try:
            while chunk := process.stdout.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
            if process.wait() != 0:
                raise ValueError("could not download the published asset for verification")
        except BaseException:
            if process.poll() is None:
                process.terminate()
            raise
    return digest.hexdigest(), size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("filename")
    parser.add_argument("size", type=int)
    parser.add_argument("sha256")
    args = parser.parse_args()
    try:
        release = json.loads(os.environ["EXISTING_RELEASE"])
        verify_asset(
            release.get("assets", []), args.filename, args.size, args.sha256,
            lambda: download_asset_hash(args.tag, args.filename, os.environ["GITHUB_REPOSITORY"]),
        )
    except (KeyError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}; preserving the existing release and skipping index update", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
