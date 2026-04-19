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


def _edit_and_publish(record_id, mutate):
    """Unlock a published record, apply `mutate(metadata) -> metadata`, re-publish."""
    status, _ = _req("POST", f"/deposit/depositions/{record_id}/actions/edit")
    if status not in (200, 201):
        return status, "edit unlock failed"
    status, dep = _req("GET", f"/deposit/depositions/{record_id}")
    if status != 200:
        return status, "get failed"
    metadata = dep.get("metadata", {})
    metadata = mutate(metadata)
    status, body = _req("PUT", f"/deposit/depositions/{record_id}",
                        data={"metadata": metadata})
    if status != 200:
        return status, f"metadata update failed: {body}"
    status, body = _req("POST", f"/deposit/depositions/{record_id}/actions/publish")
    if status not in (200, 202):
        return status, f"publish failed: {body}"
    return 0, "OK"


def cmd_update_metadata(args):
    """Overwrite specific metadata fields on a published record.

    Reads the NEW metadata values from CLI flags and merges into the existing
    metadata. Supports description, title, keywords, related_identifiers.
    Use --description-file to read HTML from disk (workflow input sizes are
    capped, so file input is safer for rich HTML).
    """
    patches = {}
    if args.description_file:
        with open(args.description_file) as f:
            patches["description"] = f.read()
    elif args.description:
        patches["description"] = args.description
    if args.title:
        patches["title"] = args.title
    if args.keywords:
        patches["keywords"] = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if args.related:
        patches["related_identifiers"] = [
            {"identifier": r.strip(), "relation": "isSupplementTo", "scheme": "url"}
            for r in args.related.split(",") if r.strip()
        ]

    if not patches:
        print("no fields to update", file=sys.stderr)
        return 1

    def mutate(md):
        md.update(patches)
        return md

    rc, msg = _edit_and_publish(args.record_id, mutate)
    if rc == 0:
        print(f"OK: record {args.record_id} metadata updated ({list(patches.keys())})")
        return 0
    print(f"FAIL {rc}: {msg}", file=sys.stderr)
    return 1


def cmd_add_to_community(args):
    """Retroactively add an already-published record to a community.

    Uses the edit → update metadata → publish cycle so only metadata changes
    (no new version). Record owner must also own the community or the
    community must auto-accept.
    """
    rid = args.record_id
    status, _ = _req("POST", f"/deposit/depositions/{rid}/actions/edit")
    if status not in (200, 201):
        print(f"edit unlock failed: {status}", file=sys.stderr)
        return 1

    status, dep = _req("GET", f"/deposit/depositions/{rid}")
    if status != 200:
        print(f"get failed: {status}", file=sys.stderr)
        return 1
    metadata = dep.get("metadata", {})

    communities = metadata.get("communities", [])
    if not any(c.get("identifier") == args.community for c in communities):
        communities.append({"identifier": args.community})
    metadata["communities"] = communities

    status, body = _req("PUT", f"/deposit/depositions/{rid}",
                        data={"metadata": metadata})
    if status != 200:
        print(f"metadata update failed: {status} {body}", file=sys.stderr)
        return 1

    status, body = _req("POST", f"/deposit/depositions/{rid}/actions/publish")
    if status not in (200, 202):
        print(f"publish failed: {status} {body}", file=sys.stderr)
        return 1
    print(f"OK: record {rid} submitted to community {args.community}")
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
    add = sub.add_parser("add-to-community",
                         help="Add an already-published record to a Zenodo community.")
    add.add_argument("record_id")
    add.add_argument("--community", required=True)
    um = sub.add_parser("update-metadata",
                        help="Overwrite metadata fields on a published record (edit→update→publish).")
    um.add_argument("record_id")
    um.add_argument("--description", default=None,
                    help="New description (HTML). Use --description-file for multi-line HTML.")
    um.add_argument("--description-file", default=None,
                    help="Path to a file whose contents become the new description.")
    um.add_argument("--title", default=None)
    um.add_argument("--keywords", default=None,
                    help="Comma-separated keyword list.")
    um.add_argument("--related", default=None,
                    help="Comma-separated URLs; each becomes a related_identifier.")
    args = p.parse_args()
    if args.cmd == "upload" and not args.creator:
        args.creator = ["JohnnyChen1113"]
    fn_name = f"cmd_{args.cmd.replace('-', '_')}"
    sys.exit(globals()[fn_name](args))


if __name__ == "__main__":
    main()
