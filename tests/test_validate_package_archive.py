import hashlib
import pathlib
import subprocess
import tarfile
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_package_archive.sh"


class ValidatePackageArchiveCliTests(unittest.TestCase):
    def test_valid_archive_reports_sha256(self):
        package = "BSgenome.Test.NCBI.One"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            package_dir = root / package
            data_dir = package_dir / "inst" / "extdata"
            data_dir.mkdir(parents=True)
            package_dir.joinpath("DESCRIPTION").write_text("Package: Test\n")
            data_dir.joinpath("single_sequences.2bit").write_bytes(b"two-bit-data")
            archive = root / f"{package}_1.0.0.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                handle.add(package_dir, arcname=package)

            result = subprocess.run(
                ["bash", str(SCRIPT), str(archive), package],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.strip(),
                hashlib.sha256(archive.read_bytes()).hexdigest(),
            )

    def test_archive_missing_twobit_member_is_rejected(self):
        package = "BSgenome.Test.NCBI.Missing"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            package_dir = root / package
            package_dir.mkdir()
            package_dir.joinpath("DESCRIPTION").write_text("Package: Test\n")
            archive = root / f"{package}_1.0.0.tar.gz"
            with tarfile.open(archive, "w:gz") as handle:
                handle.add(package_dir, arcname=package)

            result = subprocess.run(
                ["bash", str(SCRIPT), str(archive), package],
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
