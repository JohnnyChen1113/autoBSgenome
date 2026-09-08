import importlib.util
import hashlib
import io
import pathlib
import unittest
from unittest.mock import Mock, patch


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseAssetIdentityTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("release_asset", ROOT / "scripts/verify_release_asset.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.name = "BSgenome.Test.NCBI.One_1.0.0.tar.gz"
        self.sha256 = "a" * 64
        self.download = Mock(return_value=(self.sha256, 123))

    def verify(self, assets):
        return self.module.verify_asset(assets, self.name, 123, self.sha256, self.download)

    def test_matching_digest_and_filename_allow_reuse_without_download(self):
        self.verify([
            {"name": "another-file.txt", "size": 123},
            {"name": self.name, "size": 123, "digest": f"sha256:{self.sha256}"},
        ])
        self.download.assert_not_called()

    def test_equal_size_with_different_digest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.verify([{"name": self.name, "size": 123, "digest": "sha256:" + "b" * 64}])
        self.download.assert_not_called()

    def test_different_filename_is_rejected_even_when_size_and_digest_match(self):
        with self.assertRaisesRegex(ValueError, "filename"):
            self.verify([{"name": "another-version.tar.gz", "size": 123, "digest": f"sha256:{self.sha256}"}])
        self.download.assert_not_called()

    def test_missing_digest_downloads_and_verifies_bytes(self):
        self.verify([{"name": self.name, "size": 123}])
        self.download.assert_called_once_with()

    def test_downloaded_hash_mismatch_is_rejected(self):
        self.download.return_value = ("b" * 64, 123)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.verify([{"name": self.name, "size": 123}])

    def test_truncated_download_is_rejected(self):
        self.download.return_value = (self.sha256, 12)
        with self.assertRaisesRegex(ValueError, "size"):
            self.verify([{"name": self.name, "size": 123}])

    def test_streamed_download_hashes_bytes_and_uses_explicit_repository(self):
        data = b"small test archive"
        process = Mock(stdout=io.BytesIO(data))
        process.wait.return_value = 0
        context = Mock()
        context.__enter__ = Mock(return_value=process)
        context.__exit__ = Mock(return_value=False)
        with patch.object(self.module.subprocess, "Popen", return_value=context) as popen:
            result = self.module.download_asset_hash("pkg-Test", self.name, "owner/repo")
        self.assertEqual(result, (hashlib.sha256(data).hexdigest(), len(data)))
        self.assertEqual(popen.call_args.args[0], [
            "gh", "release", "download", "pkg-Test", "--repo", "owner/repo",
            "--pattern", self.name, "--output", "-",
        ])

    def test_failed_download_never_returns_a_hash(self):
        process = Mock(stdout=io.BytesIO(b"partial"))
        process.wait.return_value = 1
        context = Mock()
        context.__enter__ = Mock(return_value=process)
        context.__exit__ = Mock(return_value=False)
        with patch.object(self.module.subprocess, "Popen", return_value=context):
            with self.assertRaisesRegex(ValueError, "could not download"):
                self.module.download_asset_hash("pkg-Test", self.name, "owner/repo")


if __name__ == "__main__":
    unittest.main()
