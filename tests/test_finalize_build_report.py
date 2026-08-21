import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "finalize_build_report", ROOT / "scripts" / "finalize_build_report.py"
)
finalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finalizer)


class FinalBuildReportTests(unittest.TestCase):
    def test_archive_completion_is_separate_from_skipped_publication(self):
        metrics = {
            "schema_version": 2,
            "timings_epoch": {
                "workflow_started": 1000,
                "archive_completed": 4705,
            },
            "benchmark": {"build_sla_seconds": 3600},
            "current_stage": "publication_skipped_existing",
        }

        report = finalizer.finalize_report(
            metrics,
            workflow_status="success",
            publication_action="skip-existing",
        )

        self.assertTrue(report["outcome"]["build_complete"])
        self.assertEqual(report["timings_sec"]["workflow_to_archive"], 3705)
        self.assertTrue(report["outcome"]["build_sla_exceeded"])
        self.assertEqual(report["outcome"]["publication"], "skipped-existing")
        self.assertTrue(report["outcome"]["workflow_complete"])


if __name__ == "__main__":
    unittest.main()
