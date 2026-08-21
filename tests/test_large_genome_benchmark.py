import importlib.util
import json
import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "large_genome_benchmark",
    ROOT / "scripts" / "large_genome_benchmark.py",
)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class PublicationPolicyTests(unittest.TestCase):
    def test_only_an_exact_ncbi_accession_skips_publication(self):
        existing = [
            {"provider": "NCBI", "accession": "GCA_000404065.3"},
            {"provider": "Ensembl", "accession": "GCA_018294505.1"},
        ]

        self.assertEqual(
            benchmark.publication_action("NCBI", "GCA_000404065.3", existing),
            "skip-existing",
        )
        self.assertEqual(
            benchmark.publication_action("NCBI", "GCA_018294505.1", existing),
            "publish",
        )
        self.assertEqual(
            benchmark.publication_action("NCBI", "GCA_031772625.1", existing),
            "publish",
        )


class ManifestTests(unittest.TestCase):
    def test_curated_campaign_contains_the_16_unique_ncbi_assemblies(self):
        campaign = benchmark.load_manifest(
            ROOT / ".github" / "benchmarks" / "large-genomes-2026.json"
        )
        genomes = campaign["genomes"]

        self.assertEqual(campaign["campaign_id"], "large-genomes-2026")
        self.assertEqual(len(genomes), 16)
        self.assertEqual(len({row["accession"] for row in genomes}), 16)
        self.assertTrue(all(row["provider"] == "NCBI" for row in genomes))
        self.assertNotIn("Hordeum vulgare", {row["organism"] for row in genomes})

        by_accession = {row["accession"]: row for row in genomes}
        self.assertEqual(
            by_accession["GCA_900067695.1"]["number_of_scaffolds"], 11_340_369
        )
        self.assertEqual(
            by_accession["GCA_060040675.1"]["total_sequence_length"],
            48_146_245_579,
        )

    def test_orchestrator_order_matches_the_manifest(self):
        campaign = benchmark.load_manifest(
            ROOT / ".github" / "benchmarks" / "large-genomes-2026.json"
        )
        workflow = (
            ROOT / ".github" / "workflows" / "large-genome-benchmark-2026.yml"
        ).read_text()
        dispatched_accessions = re.findall(
            r"^\s+accession: (GCA_[0-9]+\.[0-9]+)$", workflow, re.MULTILINE
        )

        expected = [
            row["accession"]
            for row in sorted(campaign["genomes"], key=lambda row: row["order"])
        ]
        self.assertEqual(dispatched_accessions, expected)

    def test_dispatch_payload_keeps_benchmark_metadata_inside_extra(self):
        campaign = benchmark.load_manifest(
            ROOT / ".github" / "benchmarks" / "large-genomes-2026.json"
        )
        genome = next(
            row
            for row in campaign["genomes"]
            if row["accession"] == "GCA_000404065.3"
        )

        payload = benchmark.build_dispatch_payload(
            campaign, genome, publication="skip-existing"
        )

        self.assertLessEqual(len(payload), 10)
        self.assertEqual(payload["accession"], "GCA_000404065.3")
        self.assertEqual(payload["provider"], "NCBI")
        self.assertEqual(payload["package_name"], "BSgenome.Ptaeda.NCBI.Ptaeda20")
        self.assertTrue(payload["extra"]["benchmark_mode"])
        self.assertFalse(payload["extra"]["publish_to_index"])
        self.assertEqual(
            payload["extra"]["ncbi_assembly_stats"]["scaffold_n50"], 107_038
        )

    def test_campaign_plan_is_ordered_and_rechecks_the_live_catalog(self):
        campaign = benchmark.load_manifest(
            ROOT / ".github" / "benchmarks" / "large-genomes-2026.json"
        )
        catalog = {
            "flat": [
                {
                    "provider": "NCBI",
                    "accession": "GCA_000404065.3",
                },
                {
                    "provider": "NCBI",
                    "accession": "GCA_016271365.2",
                },
                {
                    "provider": "Ensembl",
                    "accession": "GCA_018294505.1",
                },
            ]
        }

        plan = benchmark.plan_campaign(campaign, catalog)

        self.assertEqual([row["order"] for row in plan], list(range(1, 17)))
        actions = {row["accession"]: row["publication"] for row in plan}
        self.assertEqual(actions["GCA_000404065.3"], "skip-existing")
        self.assertEqual(actions["GCA_016271365.2"], "skip-existing")
        self.assertEqual(actions["GCA_018294505.1"], "publish")

    def test_payload_cli_emits_a_repository_dispatch_request(self):
        catalog = {
            "flat": [
                {"provider": "NCBI", "accession": "GCA_000404065.3"}
            ]
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json") as handle:
            json.dump(catalog, handle)
            handle.flush()
            result = subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts" / "large_genome_benchmark.py"),
                    "payload",
                    "--manifest",
                    str(
                        ROOT
                        / ".github"
                        / "benchmarks"
                        / "large-genomes-2026.json"
                    ),
                    "--catalog",
                    handle.name,
                    "--accession",
                    "GCA_000404065.3",
                    "--run-token",
                    "12345",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        request = json.loads(result.stdout)
        self.assertEqual(request["event_type"], "build_bsgenome")
        payload = request["client_payload"]
        self.assertEqual(payload["job_id"], "large-genomes-2026-09-12345")
        self.assertFalse(payload["extra"]["publish_to_index"])

    def test_matrix_cli_emits_all_rows_in_campaign_order(self):
        result = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts" / "large_genome_benchmark.py"),
                "matrix",
                "--manifest",
                str(
                    ROOT
                    / ".github"
                    / "benchmarks"
                    / "large-genomes-2026.json"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        matrix = json.loads(result.stdout)
        self.assertEqual(len(matrix["include"]), 16)
        self.assertEqual(matrix["include"][0]["accession"], "GCA_963921465.1")
        self.assertEqual(matrix["include"][1]["accession"], "GCA_002915635.3")
        self.assertEqual(matrix["include"][-1]["order"], 16)

    def test_summary_keeps_missing_runs_visible(self):
        campaign = benchmark.load_manifest(
            ROOT / ".github" / "benchmarks" / "large-genomes-2026.json"
        )
        reports = {
            "GCA_000404065.3": {
                "benchmark": {"accession": "GCA_000404065.3"},
                "outcome": {
                    "build_complete": True,
                    "build_sla_exceeded": False,
                    "publication": "skipped-existing",
                    "workflow_complete": True,
                },
                "timings_sec": {"workflow_to_archive": 2100},
            }
        }

        summary = benchmark.summarize_campaign(campaign, reports)

        self.assertEqual(len(summary), 16)
        by_accession = {row["accession"]: row for row in summary}
        self.assertTrue(by_accession["GCA_000404065.3"]["build_complete"])
        self.assertEqual(
            by_accession["GCA_000404065.3"]["elapsed_seconds"], 2100
        )
        self.assertFalse(by_accession["GCA_060040675.1"]["report_available"])

    def test_summarize_cli_writes_json_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            report_dir = tmp / "reports" / "one"
            report_dir.mkdir(parents=True)
            (report_dir / "build-report.json").write_text(
                json.dumps(
                    {
                        "benchmark": {"accession": "GCA_963921465.1"},
                        "outcome": {
                            "build_complete": True,
                            "build_sla_exceeded": False,
                            "publication": "complete",
                            "workflow_complete": True,
                        },
                        "timings_sec": {"workflow_to_archive": 500},
                    }
                )
            )
            output_dir = tmp / "summary"
            subprocess.run(
                [
                    "python3",
                    str(ROOT / "scripts" / "large_genome_benchmark.py"),
                    "summarize",
                    "--manifest",
                    str(
                        ROOT
                        / ".github"
                        / "benchmarks"
                        / "large-genomes-2026.json"
                    ),
                    "--reports-dir",
                    str(tmp / "reports"),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue((output_dir / "results.json").exists())
            self.assertTrue((output_dir / "results.csv").exists())
            markdown = (output_dir / "results.md").read_text()
            self.assertIn("GCA_963921465.1", markdown)
            self.assertIn("8 min 20 s", markdown)


if __name__ == "__main__":
    unittest.main()
