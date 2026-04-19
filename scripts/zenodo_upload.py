#!/usr/bin/env python3
"""Zenodo REST API client for uploading BSgenome tarballs.

Used when a tarball exceeds the 2 GiB per-asset limit on GitHub Releases.
Zenodo allows 50 GB per record, mints a permanent DOI, and covers the
permanent-archival layer of the autoBSgenome compositional architecture.

Subcommands:
  ping     GET /api/deposit/depositions — verifies token + scope
  test     create draft, upload tiny payload, DELETE draft (no DOI minted)
  upload   full flow: create + upload + metadata + publish; prints JSON
           with doi / record_id / download_url to stdout

Env vars:
  ZENODO_TOKEN   required
  ZENODO_API     override base URL (e.g. https://sandbox.zenodo.org/api)
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("ZENODO_API", "https://zenodo.org/api").rstrip("/")


def _req(method, path, *, data=None, params=None, extra_headers=None, timeout=300):
    url = API + path
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {"Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}"}
    if extra_headers:
        headers.update(extra_headers)
    if data is not None and isinstance(data, dict):
        data = json.dumps(data).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if body and r.headers.get("Content-Type", "").startswith("application/json"):
                return r.status, json.loads(body)
            return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            body = json.loads(body)
        except Exception:
            pass
        return e.code, body


def cmd_ping(_args):
    status, body = _req("GET", "/deposit/depositions", params={"size": 1})
    if status == 200:
        count = len(body) if isinstance(body, list) else "?"
        print(f"OK api={API} token_works deposits_visible={count}")
        return 0
    print(f"FAIL status={status} body={body}", file=sys.stderr)
    return 1


def cmd_test(_args):
    status, dep = _req("POST", "/deposit/depositions", data={})
    if status not in (200, 201):
        print(f"create failed: {status} {dep}", file=sys.stderr)
        return 1
    deposit_id = dep["id"]
    bucket = dep["links"]["bucket"]
    print(f"draft_deposit_id={deposit_id}")

    content = b"autoBSgenome zenodo smoke test\n"
    put_req = urllib.request.Request(
        f"{bucket}/smoke-test.txt",
        data=content,
        headers={
            "Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}",
            "Content-Type": "application/octet-stream",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(put_req, timeout=60) as r:
            print(f"upload_status={r.status}")
    except urllib.error.HTTPError as e:
        print(f"upload failed: {e.code} {e.read()}", file=sys.stderr)
        _req("DELETE", f"/deposit/depositions/{deposit_id}")
        return 1

    status, _ = _req("DELETE", f"/deposit/depositions/{deposit_id}")
    if status in (200, 201, 204):
        print(f"cleanup_ok draft_deleted={deposit_id}")
        return 0
    print(f"cleanup warning: delete returned {status}", file=sys.stderr)
    return 0


def cmd_upload(args):
    if not os.path.exists(args.file):
        print(f"file not found: {args.file}", file=sys.stderr)
        return 1
    size = os.path.getsize(args.file)

    metadata = {
        "upload_type": "software",
        "title": args.title,
        "description": args.description,
        "creators": [{"name": c} for c in args.creator],
        "access_right": "open",
        "license": args.license,
    }
    if args.community:
        metadata["communities"] = [{"identifier": args.community}]
    if args.keywords:
        metadata["keywords"] = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if args.related:
        metadata["related_identifiers"] = [
            {"identifier": rid.strip(), "relation": "isSupplementTo", "scheme": "url"}
            for rid in args.related.split(",") if rid.strip()
        ]

    status, dep = _req("POST", "/deposit/depositions", data={})
    if status not in (200, 201):
        print(f"create failed: {status} {dep}", file=sys.stderr)
        return 1
    deposit_id = dep["id"]
    bucket = dep["links"]["bucket"]
    print(f"[zenodo] created deposit_id={deposit_id} size_gb={size/1e9:.2f}", file=sys.stderr)

    fname = os.path.basename(args.file)
    upload_url = f"{bucket}/{fname}"
    with open(args.file, "rb") as f:
        put_req = urllib.request.Request(
            upload_url,
            data=f,
            headers={
                "Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(size),
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(put_req, timeout=3600) as r:
                if r.status not in (200, 201):
                    raise RuntimeError(f"unexpected status {r.status}")
        except (urllib.error.HTTPError, RuntimeError) as e:
            print(f"[zenodo] upload failed: {e}", file=sys.stderr)
            _req("DELETE", f"/deposit/depositions/{deposit_id}")
            return 1

    status, _ = _req("PUT", f"/deposit/depositions/{deposit_id}",
                     data={"metadata": metadata})
    if status != 200:
        print(f"[zenodo] metadata attach failed: {status}", file=sys.stderr)
        _req("DELETE", f"/deposit/depositions/{deposit_id}")
        return 1

    status, pub = _req("POST", f"/deposit/depositions/{deposit_id}/actions/publish")
    if status not in (200, 202):
        print(f"[zenodo] publish failed: {status} {pub}", file=sys.stderr)
        return 1

    doi = pub.get("doi") or pub.get("conceptdoi")
    record_id = pub.get("record_id") or pub.get("id")
    download_url = f"https://zenodo.org/records/{record_id}/files/{fname}"
    print(json.dumps({
        "doi": doi,
        "record_id": record_id,
        "download_url": download_url,
        "size_bytes": size,
    }))
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    sub.add_parser("test")
    up = sub.add_parser("upload")
    up.add_argument("file")
    up.add_argument("--title", required=True)
    up.add_argument("--description", required=True)
    up.add_argument("--creator", action="append", default=None,
                    help="Author name (repeatable). Defaults to JohnnyChen1113 if omitted.")
    up.add_argument("--license", default="artistic-2.0",
                    help="Zenodo license id; default matches Bioconductor convention.")
    up.add_argument("--community", default=None)
    up.add_argument("--keywords", default=None)
    up.add_argument("--related", default=None)
    args = p.parse_args()
    if args.cmd == "upload" and not args.creator:
        args.creator = ["JohnnyChen1113"]
    sys.exit(globals()[f"cmd_{args.cmd}"](args))


if __name__ == "__main__":
    main()
