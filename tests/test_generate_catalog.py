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


if __name__ == "__main__":
    unittest.main()
