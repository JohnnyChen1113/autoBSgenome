import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ensembl_resolver", ROOT / "scripts/resolve_ensembl_fasta.py")
RESOLVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESOLVER)


class EnsemblAssemblyIdentityTests(unittest.TestCase):
    def test_authoritative_patch_alias_requires_matching_name_and_accession(self):
        metadata = {
            "assembly_name": "GRCh38.p14",
            "assembly_accession": "GCA_000001405.29",
            "default_coord_system_version": "GRCh38",
        }

        def response(url):
            if "/info/assembly/" in url:
                return 200, json.dumps(metadata)
            if "/homo_sapiens/dna/" in url:
                return 200, '<a href="Homo_sapiens.GRCh38.dna.toplevel.fa.gz">FASTA</a>'
            return 404, ""

        with patch.object(RESOLVER, "get_main_ensembl_release", return_value=115), patch.object(
            RESOLVER, "http_get", side_effect=response
        ):
            url = RESOLVER.resolve("Homo_sapiens", "vertebrates", "GCA_000001405.29", "GRCh38.p14")
            self.assertTrue(url.endswith(".GRCh38.dna.toplevel.fa.gz"))
            self.assertIsNone(RESOLVER.resolve("Homo_sapiens", "vertebrates", "GCA_000001405.28", "GRCh38.p14"))
            self.assertIsNone(RESOLVER.resolve("Homo_sapiens", "vertebrates", "GCA_000001405.29", "GRCh38.p13"))

    def test_older_requested_assembly_uses_matching_fallback_release(self):
        def response(url):
            if "/release-115/fasta/homo_sapiens/dna/" in url:
                return 200, '<a href="Homo_sapiens.GRCh38.dna.toplevel.fa.gz">FASTA</a>'
            if "/release-114/fasta/homo_sapiens/dna/" in url:
                return 200, '<a href="Homo_sapiens.GRCh37.dna.toplevel.fa.gz">FASTA</a>'
            return 404, ""

        with patch.object(RESOLVER, "get_main_ensembl_release", return_value=115), patch.object(
            RESOLVER, "http_get", side_effect=response
        ):
            url = RESOLVER.resolve("Homo_sapiens", "vertebrates", "GCA_000001405.14", "GRCh37")
        self.assertIn("/release-114/", url)
        self.assertTrue(url.endswith(".GRCh37.dna.toplevel.fa.gz"))

    def test_mismatched_assembly_is_never_returned(self):
        with patch.object(RESOLVER, "get_main_ensembl_release", return_value=115), patch.object(
            RESOLVER, "http_get", return_value=(200, '<a href="Homo_sapiens.GRCh38.dna.toplevel.fa.gz">FASTA</a>')
        ):
            self.assertIsNone(RESOLVER.resolve("Homo_sapiens", "vertebrates", "GCA_000001405.14", "GRCh37"))

    def test_filename_matching_is_exact_and_url_decoded(self):
        body = '<a href="Species.Asm10.dna.toplevel.fa.gz">wrong</a><a href="Species.Asm1%2Ev2.dna.toplevel.fa.gz">right</a>'
        with patch.object(RESOLVER, "http_get", return_value=(200, body)):
            self.assertEqual(RESOLVER.find_toplevel("https://example.org/dna/", "Asm1.v2"), "Species.Asm1%2Ev2.dna.toplevel.fa.gz")
            self.assertIsNone(RESOLVER.find_toplevel("https://example.org/dna/", "Asm1"))

    def test_collection_candidates_also_check_assembly(self):
        def response(url):
            if url.endswith("/fasta/"):
                return 200, '<a href="fungi_collection/">collection</a>'
            if url.endswith("/fungi_collection/"):
                return 200, '<a href="test_species/">species</a>'
            return 200, '<a href="Test_species.Asm2.dna.toplevel.fa.gz">FASTA</a>'

        with patch.object(RESOLVER, "http_get", side_effect=response):
            self.assertIsNone(RESOLVER.scan_collections("fungi", 62, "test_species", "GCA_000000001.1", "Asm1"))


if __name__ == "__main__":
    unittest.main()
