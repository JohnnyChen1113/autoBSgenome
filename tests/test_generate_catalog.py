import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate-catalog.py"


class GenerateCatalogTests(unittest.TestCase):
    def test_composes_fresh_ncbi_and_ensembl_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            existing = temp / "catalog.json"
            ensembl = temp / "ensembl.json"
            refseq = temp / "refseq.tsv"
            output = temp / "output.json"

            existing.write_text(
                json.dumps(
                    [
                        {
                            "a": "GCA_OLD.1",
                            "o": "Old Ensembl species",
                            "m": "Old1",
                            "g": "fungi",
                            "s": "ensembl",
                        }
                    ]
                )
            )
            ensembl_row = {
                "a": "GCA_000000002.1",
                "o": "Current Ensembl species",
                "m": "Current1",
                "g": "bacteria",
                "s": "ensembl",
                "e": "current_ensembl_species_gca_000000002",
                "d": "bacteria",
                "r": 63,
            }
            ensembl.write_text(json.dumps([ensembl_row]))
            refseq.write_text(
                "#assembly_accession\tversion_status\tgroup\trefseq_category\t"
                "organism_name\tasm_name\tgenome_size\n"
                "GCF_000000001.1\tlatest\tbacteria\treference genome\t"
                "Current NCBI species\tNCBI1\t1000000\n"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--existing-catalog",
                    str(existing),
                    "--ensembl-catalog",
                    str(ensembl),
                    "--refseq-summary",
                    str(refseq),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = json.loads(output.read_text())
            self.assertIn(ensembl_row, rows)
            self.assertFalse(any(row.get("a") == "GCA_OLD.1" for row in rows))
            self.assertTrue(any(row.get("a") == "GCF_000000001.1" for row in rows))

    def test_disambiguates_collisions_and_preserves_four_parts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            ensembl = temp / "ensembl.json"
            refseq = temp / "refseq.tsv"
            output = temp / "output.json"

            ensembl.write_text(
                json.dumps(
                    [
                        {
                            "a": accession,
                            "o": "Methanosarcina mazei",
                            "m": "gtlEnvA5udCFS",
                            "g": "bacteria",
                            "s": "ensembl",
                            "e": f"methanosarcina_mazei_{accession.lower().split('.')[0]}",
                            "d": "bacteria",
                            "r": 63,
                        }
                        for accession in ("GCA_000978935.1", "GCA_000978945.1")
                    ]
                )
            )
            refseq.write_text(
                "#assembly_accession\tversion_status\tgroup\trefseq_category\t"
                "organism_name\tasm_name\tgenome_size\n"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--ensembl-catalog",
                    str(ensembl),
                    "--refseq-summary",
                    str(refseq),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = json.loads(output.read_text())
            names = [row["p"] for row in rows]
            self.assertEqual(len(set(names)), 2)
            self.assertTrue(all(len(name.split(".")) == 4 for name in names))
            self.assertTrue(any("GCA0009789351" in name for name in names))

    def test_preserves_prior_disambiguated_name_after_collision_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            existing = temp / "catalog.json"
            ensembl = temp / "ensembl.json"
            refseq = temp / "refseq.tsv"
            output = temp / "output.json"
            retained = {
                "a": "GCA_000978935.1",
                "o": "Methanosarcina mazei",
                "m": "gtlEnvA5udCFS",
                "g": "bacteria",
                "s": "ensembl",
                "e": "methanosarcina_mazei_gca_000978935",
                "d": "bacteria",
                "r": 63,
                "p": "BSgenome.Mmazei.Ensembl.gtlEnvA5udCFSAccGCA0009789351",
            }
            existing.write_text(json.dumps([retained]))
            ensembl.write_text(json.dumps([{k: v for k, v in retained.items() if k != "p"}]))
            refseq.write_text(
                "#assembly_accession\tversion_status\tgroup\trefseq_category\t"
                "organism_name\tasm_name\tgenome_size\n"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--existing-catalog",
                    str(existing),
                    "--ensembl-catalog",
                    str(ensembl),
                    "--refseq-summary",
                    str(refseq),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())[0]["p"], retained["p"])


if __name__ == "__main__":
    unittest.main()
