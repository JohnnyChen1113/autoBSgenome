import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply-repo-index-update.py"
SPEC = importlib.util.spec_from_file_location("apply_repo_index_update", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PackageIdentityTests(unittest.TestCase):
    def test_same_accession_can_replace_existing_version(self) -> None:
        MODULE.ensure_package_identity(
            [{"package": "BSgenome.Test.NCBI.Asm", "accession": "GCF_000000001.1"}],
            "BSgenome.Test.NCBI.Asm",
            "GCF_000000001.1",
        )

    def test_different_accession_cannot_overwrite_package(self) -> None:
        with self.assertRaises(SystemExit):
            MODULE.ensure_package_identity(
                [{"package": "BSgenome.Test.NCBI.Asm", "accession": "GCF_000000001.1"}],
                "BSgenome.Test.NCBI.Asm",
                "GCF_000000002.1",
            )


if __name__ == "__main__":
    unittest.main()
