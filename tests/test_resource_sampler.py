import importlib.util
import json
import pathlib
import subprocess
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "resource_sampler", ROOT / "scripts" / "resource_sampler.py"
)
sampler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sampler)


class ResourcePeakTests(unittest.TestCase):
    def test_stage_samples_update_stage_and_global_peaks_without_losing_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = pathlib.Path(tmpdir) / "metrics.json"
            metrics_path.write_text('{"schema_version":2,"seq_count":46}')

            sampler.record_peaks(
                metrics_path,
                "forge",
                disk_used_bytes=100,
                memory_used_bytes=200,
                process_rss_bytes=150,
                samples=3,
            )
            sampler.record_peaks(
                metrics_path,
                "forge",
                disk_used_bytes=90,
                memory_used_bytes=250,
                process_rss_bytes=175,
                samples=2,
            )

            metrics = json.loads(metrics_path.read_text())
            self.assertEqual(metrics["seq_count"], 46)
            self.assertEqual(metrics["resource_peaks"]["disk_used_bytes"], 100)
            self.assertEqual(metrics["resource_peaks"]["memory_used_bytes"], 250)
            self.assertEqual(metrics["resource_peaks"]["process_rss_bytes"], 175)
            self.assertEqual(
                metrics["resource_peaks"]["stages"]["forge"],
                {
                    "disk_used_bytes": 100,
                    "memory_used_bytes": 250,
                    "process_rss_bytes": 175,
                    "samples": 5,
                },
            )

    def test_sampler_flushes_peaks_when_the_stage_terminates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = pathlib.Path(tmpdir) / "metrics.json"
            metrics_path.write_text('{"schema_version":2}')
            process = subprocess.Popen(
                [
                    "python3",
                    str(ROOT / "scripts" / "resource_sampler.py"),
                    "--stage",
                    "download",
                    "--metrics-file",
                    str(metrics_path),
                    "--path",
                    tmpdir,
                    "--interval",
                    "0.1",
                ]
            )
            time.sleep(0.25)
            process.terminate()
            self.assertEqual(process.wait(timeout=5), 0)

            metrics = json.loads(metrics_path.read_text())
            stage = metrics["resource_peaks"]["stages"]["download"]
            self.assertGreaterEqual(stage["samples"], 1)
            self.assertGreater(stage["disk_used_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
