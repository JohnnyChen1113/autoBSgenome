import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inspect_fasta.py"


class InspectFastaCliTests(unittest.TestCase):
    def run_inspection(self, contents: bytes, source: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            fasta = tmp / "genome.fa"
            report = tmp / "inspection.json"
            github_output = tmp / "github-output.txt"
            fasta.write_bytes(contents)

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    str(fasta),
                    "--source",
                    source,
                    "--json",
                    str(report),
                    "--github-output",
                    str(github_output),
                ],
                capture_output=True,
                text=True,
            )

            parsed = json.loads(report.read_text()) if report.exists() else None
            outputs = github_output.read_text() if github_output.exists() else ""
            return result, parsed, outputs

    def test_official_source_collects_build_metadata_without_base_validation(self):
        contents = b">chr1 description\nACGTN\n>chr2\nNN\n"

        result, report, outputs = self.run_inspection(contents, "ncbi")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["inspection_mode"], "metadata-only")
        self.assertFalse(report["exhaustive_validation"])
        self.assertEqual(report["seq_count"], 2)
        self.assertEqual(report["seq_ids"], ["chr1", "chr2"])
        self.assertEqual(report["fasta_size_bytes"], len(contents))
        self.assertEqual(report["sampled_bases"], 0)
        self.assertIn("seq_ids=chr1,chr2\n", outputs)
        self.assertIn("seq_count=2\n", outputs)
        self.assertIn(f"fasta_size={len(contents)}\n", outputs)

    def test_custom_source_samples_nucleotides_and_accepts_iupac_symbols(self):
        contents = b">contig-1\nACGTUNRYSWKMBDHV.-\n"

        result, report, _ = self.run_inspection(contents, "url")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["inspection_mode"], "prefix-sampled")
        self.assertEqual(report["sampled_bases"], 18)
        self.assertEqual(report["sample_limit_bases"], 1_000_000)

    def test_custom_source_rejects_fastq(self):
        result, report, _ = self.run_inspection(
            b"@read-1\nACGT\n+\n!!!!\n", "upload"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIsNone(report)
        self.assertIn("looks like FASTQ", result.stderr)

    def test_custom_source_rejects_obvious_protein_fasta(self):
        result, report, _ = self.run_inspection(
            b">protein\nMPEPTIDE\n", "url"
        )

        self.assertEqual(result.returncode, 1)
        self.assertIsNone(report)
        self.assertIn("looks like protein FASTA", result.stderr)

    def test_official_source_still_rejects_missing_sequence_data(self):
        result, report, _ = self.run_inspection(b">chr1\n", "ensembl")

        self.assertEqual(result.returncode, 1)
        self.assertIsNone(report)
        self.assertIn("no FASTA sequence data", result.stderr)

    def test_header_split_across_scan_chunks_is_counted_once(self):
        chunk_size = 16 * 1024 * 1024
        first_record_prefix = b">chr1\n"
        contents = (
            first_record_prefix
            + b"A" * (chunk_size - len(first_record_prefix) - 1)
            + b"\n>chr2\nC\n"
        )

        result, report, _ = self.run_inspection(contents, "ncbi")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["seq_count"], 2)
        self.assertEqual(report["seq_ids"], ["chr1", "chr2"])


if __name__ == "__main__":
    unittest.main()
