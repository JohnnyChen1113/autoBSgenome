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
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("ZENODO_API", "https://zenodo.org/api").rstrip("/")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _retry_delays():
    configured = os.environ.get("ZENODO_RETRY_DELAYS", "15,30,60,120")
    return [float(value) for value in configured.split(",") if value.strip()]


def _write_status(args, *, publication, failure_stage=None, deposit_id=None, **extra):
    path = getattr(args, "status_file", None)
    if not path:
        return
    payload = {
        "publication": publication,
        "failure_stage": failure_stage,
        "deposit_id": deposit_id,
        **extra,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)
        handle.write("\n")


def _retryable_error(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in RETRYABLE_STATUS_CODES
    return isinstance(
        error,
        (urllib.error.URLError, TimeoutError, ConnectionError, OSError),
    )


def _file_md5(path):
    digest = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_remote_file(deposit_id, filename):
    try:
        status, files = _req(
            "GET",
            f"/deposit/depositions/{deposit_id}/files",
        )
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None
    if status != 200 or not isinstance(files, list):
        return None
    for remote in files:
        remote_name = remote.get("filename") or remote.get("key")
        if remote_name == filename:
            return remote
    return None


def _remote_file_matches(remote, path, size):
    if not remote:
        return False
    remote_size = remote.get("filesize", remote.get("size"))
    if remote_size != size:
        return False
    checksum = remote.get("checksum", "")
    if not checksum.startswith("md5:"):
        return False
    return checksum.removeprefix("md5:").lower() == _file_md5(path).lower()


def _delete_remote_file(deposit_id, remote):
    delete_target = remote.get("links", {}).get("self")
    if not delete_target and remote.get("id"):
        delete_target = (
            f"/deposit/depositions/{deposit_id}/files/{remote['id']}"
        )
    if not delete_target:
        return False
    try:
        status, _ = _req("DELETE", delete_target)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False
    if status in (200, 201, 204, 404):
        print(
            f"[zenodo] removed incomplete remote file from deposit_id={deposit_id}",
            file=sys.stderr,
        )
        return True
    return False


def _upload_file(upload_url, path, size, deposit_id):
    delays = _retry_delays()
    attempts = len(delays) + 1
    for attempt in range(1, attempts + 1):
        try:
            with open(path, "rb") as handle:
                request = urllib.request.Request(
                    upload_url,
                    data=handle,
                    headers={
                        "Authorization": f"Bearer {os.environ['ZENODO_TOKEN']}",
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(size),
                    },
                    method="PUT",
                )
                with urllib.request.urlopen(request, timeout=3600) as response:
                    if response.status not in (200, 201):
                        raise RuntimeError(f"unexpected status {response.status}")
            return True
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            remote = _find_remote_file(deposit_id, os.path.basename(path))
            if _remote_file_matches(remote, path, size):
                print(
                    "[zenodo] upload response was lost, but the remote file is "
                    "already complete",
                    file=sys.stderr,
                )
                return True
            if remote:
                _delete_remote_file(deposit_id, remote)
            if not _retryable_error(error) or attempt == attempts:
                print(
                    f"[zenodo] upload failed after {attempt} attempt(s): {error}",
                    file=sys.stderr,
                )
                return False
            delay = delays[attempt - 1]
            print(
                f"[zenodo] transient upload failure on attempt {attempt}/{attempts}: "
                f"{error}; retrying in {delay:g}s",
                file=sys.stderr,
            )
            time.sleep(delay)


def _draft_marker(job_id):
    return f"autoBSgenome-job:{job_id}"


def _find_job_draft(job_id):
    if not job_id:
        return None
    status, deposits = _req(
        "GET",
        "/deposit/depositions",
        params={"status": "draft", "sort": "mostrecent", "size": 100},
    )
    if status != 200 or not isinstance(deposits, list):
        return None
    marker = _draft_marker(job_id)
    for deposit in deposits:
        if deposit.get("submitted"):
            continue
        if deposit.get("metadata", {}).get("notes") == marker:
            return deposit
    return None


def _create_or_recover_deposit(metadata, job_id):
    existing = _find_job_draft(job_id)
    if existing:
        print(
            f"[zenodo] reusing draft deposit_id={existing['id']} job_id={job_id}",
            file=sys.stderr,
        )
        existing["_autobsgenome_recovered"] = True
        return existing

    delays = _retry_delays()
    attempts = len(delays) + 1
    for attempt in range(1, attempts + 1):
        error = None
        try:
            status, deposit = _req(
                "POST",
                "/deposit/depositions",
                data={"metadata": metadata},
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            error = exc
            status, deposit = None, None

        if status in (200, 201):
            return deposit

        if status == 429 and attempt < attempts:
            delay = delays[attempt - 1]
            print(
                f"[zenodo] create rate limited on attempt {attempt}/{attempts}; "
                f"checking for a draft after {delay:g}s",
                file=sys.stderr,
            )
            time.sleep(delay)
            recovered = _find_job_draft(job_id)
            if recovered:
                recovered["_autobsgenome_recovered"] = True
                return recovered
            continue

        ambiguous = error is not None or status in {500, 502, 503, 504}
        if ambiguous and job_id:
            for delay in delays:
                detail = error if error is not None else status
                print(
                    f"[zenodo] ambiguous create result {detail}; checking for "
                    f"job draft after {delay:g}s",
                    file=sys.stderr,
                )
                time.sleep(delay)
                recovered = _find_job_draft(job_id)
                if recovered:
                    print(
                        f"[zenodo] recovered draft deposit_id={recovered['id']} "
                        f"job_id={job_id}",
                        file=sys.stderr,
                    )
                    recovered["_autobsgenome_recovered"] = True
                    return recovered

        detail = error if error is not None else f"status={status} body={deposit}"
        print(f"[zenodo] create failed: {detail}", file=sys.stderr)
        return None

    return None


def _delete_draft(deposit_id):
    try:
        status, body = _req("DELETE", f"/deposit/depositions/{deposit_id}")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
        print(
            f"[zenodo] cleanup failed for draft deposit_id={deposit_id}: {error}",
            file=sys.stderr,
        )
        return False
    if status in (200, 201, 204, 404):
        print(f"[zenodo] deleted draft deposit_id={deposit_id}", file=sys.stderr)
        return True
    print(
        f"[zenodo] cleanup failed for draft deposit_id={deposit_id}: "
        f"status={status} body={body}",
        file=sys.stderr,
    )
    return False


def _published_deposit(deposit_id):
    try:
        status, deposit = _req(
            "GET",
            f"/deposit/depositions/{deposit_id}",
        )
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None
    if status != 200 or not isinstance(deposit, dict):
        return None
    if deposit.get("submitted") or deposit.get("state") == "done":
        return deposit
    return None


def _request_with_retry(
    method,
    path,
    *,
    stage,
    success_statuses,
    data=None,
):
    delays = _retry_delays()
    attempts = len(delays) + 1
    for attempt in range(1, attempts + 1):
        error = None
        try:
            status, body = _req(method, path, data=data)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            error = exc
            status, body = None, None
        if status in success_statuses:
            return status, body
        retryable = error is not None or status in RETRYABLE_STATUS_CODES
        if not retryable or attempt == attempts:
            detail = error if error is not None else f"status={status} body={body}"
            print(
                f"[zenodo] {stage} failed after {attempt} attempt(s): {detail}",
                file=sys.stderr,
            )
            return status, body
        delay = delays[attempt - 1]
        print(
            f"[zenodo] transient {stage} failure on attempt {attempt}/{attempts}; "
            f"retrying in {delay:g}s",
            file=sys.stderr,
        )
        time.sleep(delay)


def _publish_deposit(deposit_id):
    delays = _retry_delays()
    attempts = len(delays) + 1
    path = f"/deposit/depositions/{deposit_id}/actions/publish"
    for attempt in range(1, attempts + 1):
        error = None
        try:
            status, published = _req("POST", path)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            error = exc
            status, published = None, None

        if status in (200, 202):
            return published

        reconciled = _published_deposit(deposit_id)
        if reconciled:
            print(
                f"[zenodo] publish response was lost; recovered published "
                f"record_id={reconciled.get('record_id', reconciled.get('id'))}",
                file=sys.stderr,
            )
            return reconciled

        retryable = error is not None or status in RETRYABLE_STATUS_CODES
        if not retryable or attempt == attempts:
            detail = error if error is not None else f"status={status} body={published}"
            print(
                f"[zenodo] publish failed after {attempt} attempt(s) for "
                f"deposit_id={deposit_id}: {detail}",
                file=sys.stderr,
            )
            return None

        delay = delays[attempt - 1]
        print(
            f"[zenodo] transient publish failure on attempt {attempt}/{attempts}; "
            f"retrying in {delay:g}s",
            file=sys.stderr,
        )
        time.sleep(delay)


def _req(method, path, *, data=None, params=None, extra_headers=None, timeout=300):
    url = path if path.startswith(("http://", "https://")) else API + path
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
        _write_status(args, publication="failed", failure_stage="zenodo_input")
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
    if args.job_id:
        metadata["notes"] = _draft_marker(args.job_id)

    _write_status(
        args,
        publication="in_progress",
        stage="zenodo_create",
    )
    dep = _create_or_recover_deposit(metadata, args.job_id)
    if dep is None:
        _write_status(args, publication="failed", failure_stage="zenodo_create")
        return 1
    deposit_id = dep["id"]
    bucket = dep["links"]["bucket"]
    print(f"[zenodo] created deposit_id={deposit_id} size_gb={size/1e9:.2f}", file=sys.stderr)

    fname = os.path.basename(args.file)
    upload_url = f"{bucket}/{fname}"
    _write_status(
        args,
        publication="in_progress",
        stage="zenodo_upload",
        deposit_id=deposit_id,
    )
    remote_file = None
    if dep.get("_autobsgenome_recovered"):
        remote_file = _find_remote_file(deposit_id, fname)
    if _remote_file_matches(remote_file, args.file, size):
        print(
            f"[zenodo] reusing complete remote file from deposit_id={deposit_id}",
            file=sys.stderr,
        )
        uploaded = True
    else:
        if remote_file:
            _delete_remote_file(deposit_id, remote_file)
        uploaded = _upload_file(upload_url, args.file, size, deposit_id)
    if not uploaded:
        cleanup_complete = _delete_draft(deposit_id)
        _write_status(
            args,
            publication="failed",
            failure_stage="zenodo_upload",
            deposit_id=None if cleanup_complete else deposit_id,
            draft_cleanup="deleted" if cleanup_complete else "failed",
        )
        return 1

    _write_status(
        args,
        publication="in_progress",
        stage="zenodo_metadata",
        deposit_id=deposit_id,
    )
    status, _ = _request_with_retry(
        "PUT",
        f"/deposit/depositions/{deposit_id}",
        stage="metadata update",
        success_statuses={200},
        data={"metadata": metadata},
    )
    if status != 200:
        _write_status(
            args,
            publication="failed",
            failure_stage="zenodo_metadata",
            deposit_id=deposit_id,
        )
        print(
            f"[zenodo] retaining draft deposit_id={deposit_id} after metadata failure",
            file=sys.stderr,
        )
        return 1

    _write_status(
        args,
        publication="in_progress",
        stage="zenodo_publish",
        deposit_id=deposit_id,
    )
    pub = _publish_deposit(deposit_id)
    if pub is None:
        _write_status(
            args,
            publication="failed",
            failure_stage="zenodo_publish",
            deposit_id=deposit_id,
        )
        return 1

    doi = (
        pub.get("doi")
        or pub.get("conceptdoi")
        or pub.get("metadata", {}).get("prereserve_doi", {}).get("doi")
    )
    record_id = pub.get("record_id") or pub.get("id")
    download_url = f"https://zenodo.org/records/{record_id}/files/{fname}"
    _write_status(
        args,
        publication="complete",
        deposit_id=deposit_id,
        record_id=record_id,
        doi=doi,
        download_url=download_url,
    )
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
    up.add_argument(
        "--job-id",
        default=None,
        help="Stable build job identifier used to recover ambiguous Zenodo drafts.",
    )
    up.add_argument(
        "--status-file",
        default=None,
        help="Optional JSON file receiving publication stage and recovery details.",
    )
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
