import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "resolve_ncbi_fasta.py"


class ResolveNcbiFastaCliTests(unittest.TestCase):
    def test_resolves_versioned_accession_to_genomic_fasta_and_md5(self):
        accession = "GCA_963921465.1"
        directory_name = (
            "GCA_963921465.1_WRC_timopheevii_genome_with_organelles"
        )
        fasta_name = f"{directory_name}_genomic.fna.gz"
        stats_name = f"{directory_name}_assembly_stats.txt"
        expected_md5 = "0123456789abcdef0123456789abcdef"

        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            assembly_dir = (
                root
                / "genomes"
                / "all"
                / "GCA"
                / "963"
                / "921"
                / "465"
                / directory_name
            )
            assembly_dir.mkdir(parents=True)
            (assembly_dir / fasta_name).write_bytes(b"")
            (assembly_dir / stats_name).write_text(
                "all\tall\tall\tall\ttotal-length\t9351419471\n"
            )
            (assembly_dir / "md5checksums.txt").write_text(
                f"{expected_md5}  ./{fasta_name}\n"
            )
            assembly_dir.joinpath("index.html").write_text(
                f'<a href="{fasta_name}">{fasta_name}</a>\n'
                f'<a href="{stats_name}">{stats_name}</a>\n'
                '<a href="md5checksums.txt">md5checksums.txt</a>\n'
            )
            assembly_dir.parent.joinpath("index.html").write_text(
                f'<a href="{directory_name}/">{directory_name}/</a>\n'
            )

            ftp_base = root.joinpath("genomes", "all").as_uri()
            report_path = root / "resolved.json"
            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT),
                    accession,
                    "--ftp-base",
                    ftp_base,
                    "--json",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["accession"], accession)
            self.assertEqual(report["expected_md5"], expected_md5)
            self.assertEqual(report["total_sequence_length"], 9_351_419_471)
            self.assertEqual(
                report["fasta_url"],
                f"{ftp_base}/GCA/963/921/465/{directory_name}/{fasta_name}",
            )


if __name__ == "__main__":
    unittest.main()
