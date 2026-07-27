import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate-ensembl-catalog.py"
HEADER = (
    "#name\tspecies\tdivision\ttaxonomy_id\tassembly\tassembly_accession\t"
    "genebuild\tvariation\tmicroarray\tpan_compara\tpeptide_compara\t"
    "genome_alignments\tother_alignments\tcore_db\tspecies_id\n"
)


def species_row(
    name: str,
    species: str,
    division: str,
    assembly: str,
    accession: str,
) -> str:
    return (
        f"{name}\t{species}\t{division}\t1\t{assembly}\t{accession}\t"
        "build\tN\tN\tN\tN\tN\tN\tcore\t1\n"
    )


class GenerateEnsemblCatalogTests(unittest.TestCase):
    def test_generates_compact_rows_for_vertebrates_and_bacteria(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            vertebrates = temp / "vertebrates.tsv"
            bacteria = temp / "bacteria.tsv"
            output = temp / "ensembl.json"
            state_output = temp / "state.json"

            vertebrates.write_text(
                HEADER
                + species_row(
                    "Zebrafish",
                    "danio_rerio",
                    "EnsemblVertebrates",
                    "GRCz11",
                    "GCA_000002035.4",
                )
            )
            bacteria.write_text(
                HEADER
                + species_row(
                    "Abditibacterium utsteinense (GCA_002973605)",
                    "abditibacterium_utsteinense_gca_002973605",
                    "EnsemblBacteria",
                    "ASM297360v1",
                    "GCA_002973605.1",
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    f"vertebrates={vertebrates}",
                    "--source",
                    f"bacteria={bacteria}",
                    "--release-main",
                    "116",
                    "--release-genomes",
                    "63",
                    "--minimum",
                    "vertebrates=1",
                    "--minimum",
                    "bacteria=1",
                    "--output",
                    str(output),
                    "--state-output",
                    str(state_output),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(output.read_text()),
                [
                    {
                        "a": "GCA_002973605.1",
                        "o": "Abditibacterium utsteinense",
                        "m": "ASM297360v1",
                        "g": "bacteria",
                        "s": "ensembl",
                        "e": "abditibacterium_utsteinense_gca_002973605",
                        "d": "bacteria",
                        "r": 63,
                    },
                    {
                        "a": "GCA_000002035.4",
                        "o": "Danio rerio",
                        "m": "GRCz11",
                        "g": "vertebrate_other",
                        "s": "ensembl",
                        "e": "danio_rerio",
                        "d": "vertebrates",
                        "r": 116,
                    },
                ],
            )

    def test_removes_a_missing_upstream_row_only_after_two_successful_syncs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bacteria = temp / "bacteria.tsv"
            previous = temp / "previous.json"
            state = temp / "state.json"
            first_output = temp / "first.json"
            first_state = temp / "first-state.json"
            second_output = temp / "second.json"
            second_state = temp / "second-state.json"

            bacteria.write_text(
                HEADER
                + species_row(
                    "Current bacterium (GCA_000000002)",
                    "current_bacterium_gca_000000002",
                    "EnsemblBacteria",
                    "Current1",
                    "GCA_000000002.1",
                )
            )
            missing_row = {
                "a": "GCA_000000001.1",
                "o": "Missing bacterium",
                "m": "Missing1",
                "g": "bacteria",
                "s": "ensembl",
                "e": "missing_bacterium_gca_000000001",
                "d": "bacteria",
                "r": 62,
            }
            previous.write_text(json.dumps([missing_row]))
            state.write_text(json.dumps({"version": 1, "missing_counts": {}}))

            common = [
                sys.executable,
                str(SCRIPT),
                "--source",
                f"bacteria={bacteria}",
                "--release-main",
                "116",
                "--release-genomes",
                "63",
                "--minimum",
                "bacteria=1",
            ]
            first = subprocess.run(
                [
                    *common,
                    "--previous",
                    str(previous),
                    "--state",
                    str(state),
                    "--output",
                    str(first_output),
                    "--state-output",
                    str(first_state),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn(missing_row, json.loads(first_output.read_text()))

            second = subprocess.run(
                [
                    *common,
                    "--previous",
                    str(first_output),
                    "--state",
                    str(first_state),
                    "--output",
                    str(second_output),
                    "--state-output",
                    str(second_state),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertNotIn(missing_row, json.loads(second_output.read_text()))

    def test_rejects_a_division_that_drops_more_than_the_safety_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            fungi = temp / "fungi.tsv"
            state = temp / "state.json"
            fungi.write_text(
                HEADER
                + species_row(
                    "Current fungus",
                    "current_fungus",
                    "EnsemblFungi",
                    "Current1",
                    "GCA_000000010.1",
                )
            )
            state.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "counts": {"fungi": 20},
                        "missing_counts": {},
                    }
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    f"fungi={fungi}",
                    "--release-main",
                    "116",
                    "--release-genomes",
                    "63",
                    "--minimum",
                    "fungi=1",
                    "--state",
                    str(state),
                    "--output",
                    str(temp / "output.json"),
                    "--state-output",
                    str(temp / "next-state.json"),
                ],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fungi dropped", result.stderr)

    def test_enriches_scientific_name_and_genome_size_from_ncbi_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            vertebrates = temp / "vertebrates.tsv"
            summary = temp / "assembly_summary.tsv"
            output = temp / "output.json"
            vertebrates.write_text(
                HEADER
                + species_row(
                    "Three-toed box turtle",
                    "terrapene_carolina_triunguis",
                    "EnsemblVertebrates",
                    "T_m_triunguis-2.0",
                    "GCA_002925995.2",
                )
            )
            summary.write_text(
                "# assembly_accession\torganism_name\tgenome_size\n"
                "GCA_002925995.2\tTerrapene carolina triunguis\t2350000000\n"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--source",
                    f"vertebrates={vertebrates}",
                    "--assembly-summary",
                    str(summary),
                    "--release-main",
                    "116",
                    "--release-genomes",
                    "63",
                    "--minimum",
                    "vertebrates=1",
                    "--output",
                    str(output),
                    "--state-output",
                    str(temp / "state.json"),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads(output.read_text())[0]
            self.assertEqual(row["o"], "Terrapene carolina triunguis")
            self.assertEqual(row["z"], 2350.0)


if __name__ == "__main__":
    unittest.main()
