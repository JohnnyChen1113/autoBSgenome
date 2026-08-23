import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import ssl
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "zenodo_upload",
    ROOT / "scripts" / "zenodo_upload.py",
)
zenodo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zenodo)


class FakeResponse:
    def __init__(self, status, body=None):
        self.status = status
        self.body = json.dumps(body or {}).encode("utf-8")
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


def upload_args(package, status_file=None):
    return argparse.Namespace(
        file=str(package),
        title="Test package",
        description="Test description",
        creator=["Test Author"],
        license="artistic-2.0",
        community=None,
        keywords=None,
        related=None,
        job_id="test-job",
        status_file=str(status_file) if status_file else None,
    )


class ZenodoUploadTests(unittest.TestCase):
    def test_reused_draft_skips_upload_when_the_remote_file_is_complete(self):
        content = b"x" * 4096
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        recovered = {
            "id": 909,
            "links": {"bucket": "https://zenodo.test/api/files/recovered"},
            "metadata": {"notes": "autoBSgenome-job:test-job"},
            "submitted": False,
        }
        responses = [
            FakeResponse(200, [recovered]),
            FakeResponse(
                200,
                [
                    {
                        "filename": "package.tar.gz",
                        "filesize": len(content),
                        "checksum": f"md5:{checksum}",
                    }
                ],
            ),
            FakeResponse(200),
            FakeResponse(202, {"doi": "10.5281/zenodo.909", "record_id": 909}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(content)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0,0,0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        upload_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "PUT"
            and "/api/files/" in urllib.parse.urlparse(call.args[0].full_url).path
        ]
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(upload_calls, [])
        self.assertIn("reusing complete remote file", stderr.getvalue())

    def test_upload_retries_after_the_connection_closes_mid_put(self):
        created = FakeResponse(
            201,
            {
                "id": 101,
                "links": {"bucket": "https://zenodo.test/api/files/bucket"},
            },
        )
        ssl_eof = urllib.error.URLError(
            ssl.SSLEOFError(8, "EOF occurred in violation of protocol")
        )
        responses = [
            FakeResponse(200, []),
            created,
            ssl_eof,
            FakeResponse(200, []),
            FakeResponse(200, {"size": 4096, "checksum": "md5:unused"}),
            FakeResponse(200),
            FakeResponse(202, {"doi": "10.5281/zenodo.101", "record_id": 101}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(b"x" * 4096)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0,0,0",
                    },
                ),
                mock.patch.object(zenodo.urllib.request, "urlopen", side_effect=responses),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["record_id"], 101)

    def test_lost_upload_response_accepts_a_complete_remote_file(self):
        created = FakeResponse(
            201,
            {
                "id": 303,
                "links": {"bucket": "https://zenodo.test/api/files/bucket"},
            },
        )
        connection_lost = urllib.error.URLError("connection reset after upload")
        content = b"x" * 4096
        checksum = hashlib.md5(content, usedforsecurity=False).hexdigest()
        responses = [
            FakeResponse(200, []),
            created,
            connection_lost,
            FakeResponse(
                200,
                [
                    {
                        "filename": "package.tar.gz",
                        "filesize": len(content),
                        "checksum": f"md5:{checksum}",
                    }
                ],
            ),
            FakeResponse(200),
            FakeResponse(202, {"doi": "10.5281/zenodo.303", "record_id": 303}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(content)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0,0,0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        upload_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "PUT"
            and "/api/files/" in urllib.parse.urlparse(call.args[0].full_url).path
        ]
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(len(upload_calls), 1)
        self.assertIn("remote file is already complete", stderr.getvalue())

    def test_incomplete_remote_file_is_deleted_before_upload_retry(self):
        created = FakeResponse(
            201,
            {
                "id": 505,
                "links": {"bucket": "https://zenodo.test/api/files/bucket"},
            },
        )
        responses = [
            FakeResponse(200, []),
            created,
            urllib.error.URLError("connection reset"),
            FakeResponse(
                200,
                [
                    {
                        "id": "partial-file",
                        "filename": "package.tar.gz",
                        "filesize": 1024,
                        "checksum": "md5:partial",
                    }
                ],
            ),
            FakeResponse(204),
            FakeResponse(200, {"size": 4096, "checksum": "md5:unused"}),
            FakeResponse(200),
            FakeResponse(202, {"doi": "10.5281/zenodo.505", "record_id": 505}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(b"x" * 4096)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0,0,0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        partial_delete_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "DELETE"
            and urllib.parse.urlparse(call.args[0].full_url).path
            == "/api/deposit/depositions/505/files/partial-file"
        ]
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(len(partial_delete_calls), 1)
        self.assertIn("removed incomplete remote file", stderr.getvalue())

    def test_lost_publish_response_reuses_the_published_record(self):
        created = FakeResponse(
            201,
            {
                "id": 606,
                "links": {"bucket": "https://zenodo.test/api/files/bucket"},
            },
        )
        responses = [
            FakeResponse(200, []),
            created,
            FakeResponse(200, {"size": 4096, "checksum": "md5:unused"}),
            FakeResponse(200),
            urllib.error.URLError("publish response lost"),
            FakeResponse(
                200,
                {
                    "id": 606,
                    "record_id": 606,
                    "doi": "10.5281/zenodo.606",
                    "submitted": True,
                    "state": "done",
                },
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(b"x" * 4096)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0,0,0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        publish_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "POST"
            and urllib.parse.urlparse(call.args[0].full_url).path
            == "/api/deposit/depositions/606/actions/publish"
        ]
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(len(publish_calls), 1)
        self.assertEqual(json.loads(stdout.getvalue())["record_id"], 606)

    def test_metadata_update_retries_a_transient_server_error(self):
        created = FakeResponse(
            201,
            {
                "id": 707,
                "links": {"bucket": "https://zenodo.test/api/files/bucket"},
            },
        )
        metadata_error = urllib.error.HTTPError(
            "https://zenodo.test/api/deposit/depositions/707",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b"unavailable"),
        )
        responses = [
            FakeResponse(200, []),
            created,
            FakeResponse(200, {"size": 4096, "checksum": "md5:unused"}),
            metadata_error,
            FakeResponse(200),
            FakeResponse(202, {"doi": "10.5281/zenodo.707", "record_id": 707}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(b"x" * 4096)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0,0,0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        metadata_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "PUT"
            and urllib.parse.urlparse(call.args[0].full_url).path
            == "/api/deposit/depositions/707"
        ]
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(len(metadata_calls), 2)

    def test_rate_limited_create_retries_without_duplicate_drafts(self):
        rate_limited = urllib.error.HTTPError(
            "https://zenodo.test/api/deposit/depositions",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b"rate limited"),
        )
        created = FakeResponse(
            201,
            {
                "id": 808,
                "links": {"bucket": "https://zenodo.test/api/files/bucket"},
            },
        )
        responses = [
            FakeResponse(200, []),
            rate_limited,
            FakeResponse(200, []),
            created,
            FakeResponse(200, {"size": 4096, "checksum": "md5:unused"}),
            FakeResponse(200),
            FakeResponse(202, {"doi": "10.5281/zenodo.808", "record_id": 808}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(b"x" * 4096)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        create_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "POST"
            and urllib.parse.urlparse(call.args[0].full_url).path
            == "/api/deposit/depositions"
        ]
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(len(create_calls), 2)

    def test_create_timeout_recovers_the_job_draft_without_creating_twice(self):
        marker = "autoBSgenome-job:test-job"
        recovered = {
            "id": 202,
            "links": {"bucket": "https://zenodo.test/api/files/recovered"},
            "metadata": {"notes": marker},
            "submitted": False,
        }
        timeout = urllib.error.HTTPError(
            "https://zenodo.test/api/deposit/depositions",
            504,
            "Gateway Time-out",
            {},
            io.BytesIO(b"gateway timeout"),
        )
        responses = [
            FakeResponse(200, []),
            timeout,
            FakeResponse(200, [recovered]),
            FakeResponse(200, []),
            FakeResponse(200, {"size": 4096, "checksum": "md5:unused"}),
            FakeResponse(200),
            FakeResponse(202, {"doi": "10.5281/zenodo.202", "record_id": 202}),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(b"x" * 4096)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0,0,0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package))

        create_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "POST"
            and urllib.parse.urlparse(call.args[0].full_url).path
            == "/api/deposit/depositions"
        ]
        self.assertEqual(result, 0, stderr.getvalue())
        self.assertEqual(len(create_calls), 1)
        self.assertEqual(json.loads(stdout.getvalue())["record_id"], 202)

    def test_exhausted_upload_reports_the_draft_when_cleanup_fails(self):
        created = FakeResponse(
            201,
            {
                "id": 404,
                "links": {"bucket": "https://zenodo.test/api/files/bucket"},
            },
        )
        first_error = urllib.error.URLError("first connection reset")
        second_error = urllib.error.URLError("second connection reset")
        cleanup_error = urllib.error.HTTPError(
            "https://zenodo.test/api/deposit/depositions/404",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b"unavailable"),
        )
        responses = [
            FakeResponse(200, []),
            created,
            first_error,
            FakeResponse(200, []),
            second_error,
            FakeResponse(200, []),
            cleanup_error,
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            package = pathlib.Path(tmpdir) / "package.tar.gz"
            package.write_bytes(b"x" * 4096)
            status_file = pathlib.Path(tmpdir) / "zenodo-status.json"
            stderr = io.StringIO()
            with (
                mock.patch.dict(
                    "os.environ",
                    {
                        "ZENODO_TOKEN": "test-token",
                        "ZENODO_RETRY_DELAYS": "0",
                    },
                ),
                mock.patch.object(
                    zenodo.urllib.request,
                    "urlopen",
                    side_effect=responses,
                ) as urlopen,
                contextlib.redirect_stderr(stderr),
            ):
                result = zenodo.cmd_upload(upload_args(package, status_file))
            publication_status = json.loads(status_file.read_text())

        delete_calls = [
            call
            for call in urlopen.call_args_list
            if call.args[0].get_method() == "DELETE"
            and urllib.parse.urlparse(call.args[0].full_url).path
            == "/api/deposit/depositions/404"
        ]
        self.assertEqual(result, 1)
        self.assertEqual(len(delete_calls), 1)
        self.assertIn("cleanup failed for draft deposit_id=404", stderr.getvalue())
        self.assertEqual(publication_status["failure_stage"], "zenodo_upload")
        self.assertEqual(publication_status["deposit_id"], 404)


if __name__ == "__main__":
    unittest.main()
