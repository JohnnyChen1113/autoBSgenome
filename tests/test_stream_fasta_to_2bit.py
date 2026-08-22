import gzip
import hashlib
import json
import pathlib
import subprocess
import tempfile
import textwrap
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "stream_fasta_to_2bit.py"


class StreamFastaToTwoBitCliTests(unittest.TestCase):
    def test_gzip_stream_is_inspected_and_forwarded_to_converter(self):
        fasta = b">chr1 description\nACGTN\n>chr2\nNN\n"
        compressed = gzip.compress(fasta, mtime=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            converter = tmp / "fake-faToTwoBit"
            converter.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import pathlib
                    import sys

                    assert sys.argv[-2] == "stdin"
                    pathlib.Path(sys.argv[-1]).write_bytes(sys.stdin.buffer.read())
                    """
                )
            )
            converter.chmod(0o755)
            output = tmp / "genome.2bit"
            report_path = tmp / "inspection.json"
            github_output = tmp / "github-output.txt"

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--source",
                    "ncbi",
                    "--output",
                    str(output),
                    "--expected-md5",
                    hashlib.md5(compressed).hexdigest(),
                    "--json",
                    str(report_path),
                    "--github-output",
                    str(github_output),
                    "--converter",
                    str(converter),
                ],
                input=compressed,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(output.read_bytes(), fasta)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["seq_count"], 2)
            self.assertEqual(report["seq_ids"], ["chr1", "chr2"])
            self.assertEqual(report["fasta_size_bytes"], len(fasta))
            self.assertEqual(report["compressed_size_bytes"], len(compressed))
            self.assertEqual(report["compressed_md5"], hashlib.md5(compressed).hexdigest())
            self.assertEqual(report["twobit_size_bytes"], len(fasta))
            self.assertIn("seq_ids=chr1,chr2\n", github_output.read_text())

    def test_md5_mismatch_fails_and_removes_partial_2bit(self):
        fasta = b">chr1\nACGT\n"
        compressed = gzip.compress(fasta, mtime=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            converter = tmp / "fake-faToTwoBit"
            converter.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "pathlib.Path(sys.argv[-1]).write_bytes(sys.stdin.buffer.read())\n"
            )
            converter.chmod(0o755)
            output = tmp / "genome.2bit"
            report_path = tmp / "inspection.json"

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--source",
                    "ncbi",
                    "--output",
                    str(output),
                    "--expected-md5",
                    "0" * 32,
                    "--json",
                    str(report_path),
                    "--converter",
                    str(converter),
                ],
                input=compressed,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(b"compressed MD5 mismatch", result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse(report_path.exists())

    def test_converter_failure_propagates_and_removes_partial_output(self):
        fasta = b">chr1\nACGT\n"
        compressed = gzip.compress(fasta, mtime=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            converter = tmp / "failing-faToTwoBit"
            converter.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "pathlib.Path(sys.argv[-1]).write_bytes(b'partial')\n"
                "sys.stdin.buffer.read()\n"
                "raise SystemExit(7)\n"
            )
            converter.chmod(0o755)
            output = tmp / "genome.2bit"

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--source",
                    "ncbi",
                    "--output",
                    str(output),
                    "--expected-md5",
                    hashlib.md5(compressed).hexdigest(),
                    "--converter",
                    str(converter),
                ],
                input=compressed,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(b"faToTwoBit exited with status 7", result.stderr)
            self.assertFalse(output.exists())

    def test_truncated_gzip_fails_and_removes_partial_output(self):
        truncated = gzip.compress(b">chr1\nACGT\n", mtime=0)[:-5]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            converter = tmp / "fake-faToTwoBit"
            converter.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "pathlib.Path(sys.argv[-1]).write_bytes(sys.stdin.buffer.read())\n"
            )
            converter.chmod(0o755)
            output = tmp / "genome.2bit"

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    "--source",
                    "ncbi",
                    "--output",
                    str(output),
                    "--expected-md5",
                    hashlib.md5(truncated).hexdigest(),
                    "--converter",
                    str(converter),
                ],
                input=truncated,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn(b"streaming FASTA conversion failed", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
