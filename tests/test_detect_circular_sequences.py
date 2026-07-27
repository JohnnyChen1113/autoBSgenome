import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "detect_circular_sequences.py"
SPEC = importlib.util.spec_from_file_location("detect_circular_sequences", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class DetectCircularSequenceTests(unittest.TestCase):
    def test_detects_circular_chromosome_and_uses_actual_fasta_id(self) -> None:
        reports = [
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Chromosome",
                "refseq_accession": "NC_000913.3",
                "genbank_accession": "U00096.3",
                "chr_name": "chromosome",
            }
        ]
        with patch.object(
            MODULE,
            "fetch_topologies",
            return_value={"NC_000913.3": "circular"},
        ):
            self.assertEqual(
                MODULE.detect(reports, ["NC_000913.3"], "ncbi"),
                ["NC_000913.3"],
            )

    def test_ensembl_mapping_prefers_chromosome_name(self) -> None:
        reports = [
            {
                "role": "assembled-molecule",
                "assigned_molecule_location_type": "Mitochondrion",
                "refseq_accession": "NC_012920.1",
                "genbank_accession": "J01415.2",
                "chr_name": "MT",
            }
        ]
        with patch.object(
            MODULE,
            "fetch_topologies",
            return_value={"NC_012920.1": "circular"},
        ):
            self.assertEqual(MODULE.detect(reports, ["1", "MT"], "ensembl"), ["MT"])

    def test_linear_molecule_is_not_marked_circular(self) -> None:
        reports = [
            {
                "role": "assembled-molecule",
                "refseq_accession": "NC_LINEAR.1",
                "chr_name": "1",
            }
        ]
        with patch.object(
            MODULE,
            "fetch_topologies",
            return_value={"NC_LINEAR.1": "linear"},
        ):
            self.assertEqual(MODULE.detect(reports, ["NC_LINEAR.1"], "ncbi"), [])

    def test_circular_record_without_fasta_match_fails(self) -> None:
        reports = [
            {
                "role": "assembled-molecule",
                "refseq_accession": "NC_000001.1",
            }
        ]
        with patch.object(
            MODULE,
            "fetch_topologies",
            return_value={"NC_000001.1": "circular"},
        ):
            with self.assertRaises(MODULE.DetectionError):
                MODULE.detect(reports, ["different"], "ncbi")


if __name__ == "__main__":
    unittest.main()
