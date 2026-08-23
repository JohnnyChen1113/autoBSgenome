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
    def test_curated_campaign_contains_the_20_unique_ncbi_assemblies(self):
        campaign = benchmark.load_manifest(
            ROOT / ".github" / "benchmarks" / "large-genomes-2026.json"
        )
        genomes = campaign["genomes"]

        self.assertEqual(campaign["campaign_id"], "large-genomes-2026")
        self.assertEqual(len(genomes), 20)
        self.assertEqual(len({row["accession"] for row in genomes}), 20)
        self.assertTrue(all(row["provider"] == "NCBI" for row in genomes))
        self.assertNotIn("Hordeum vulgare", {row["organism"] for row in genomes})

        by_accession = {row["accession"]: row for row in genomes}
        self.assertEqual(
            by_accession["GCA_047292645.1"]["number_of_scaffolds"], 9_389_658
        )
        self.assertEqual(
            by_accession["GCA_963277665.1"]["total_sequence_length"],
            94_261_041_113,
        )
        self.assertNotIn("GCA_040438655.1", by_accession)
        self.assertNotIn("GCA_963082535.1", by_accession)
        self.assertEqual(
            by_accession["GCA_000404065.3"]["publication_policy"], "never"
        )
        self.assertEqual(
            by_accession["GCA_016271365.2"]["publication_policy"], "never"
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

    def test_orchestrator_can_stop_after_the_initial_three_item_batch(self):
        workflow = (
            ROOT / ".github" / "workflows" / "large-genome-benchmark-2026.yml"
        ).read_text()

        self.assertIn("through_order:", workflow)
        self.assertIn("default: 20", workflow)
        self.assertIn(
            "if: ${{ always() && inputs.through_order >= 3 }}", workflow
        )
        self.assertIn(
            "if: ${{ always() && inputs.through_order >= 4 }}", workflow
        )

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
            campaign, genome, publication="skip-policy"
        )

        self.assertLessEqual(len(payload), 10)
        self.assertEqual(payload["accession"], "GCA_000404065.3")
        self.assertEqual(payload["provider"], "NCBI")
        self.assertEqual(payload["package_name"], "BSgenome.Ptaeda.NCBI.Ptaeda20")
        self.assertTrue(payload["extra"]["benchmark_mode"])
        self.assertFalse(payload["extra"]["publish_to_index"])
        self.assertEqual(
            payload["extra"]["benchmark_publication_action"], "skip-policy"
        )
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

        self.assertEqual([row["order"] for row in plan], list(range(1, 21)))
        actions = {row["accession"]: row["publication"] for row in plan}
        self.assertEqual(actions["GCA_000404065.3"], "skip-policy")
        self.assertEqual(actions["GCA_016271365.2"], "skip-policy")
        self.assertEqual(actions["GCA_054660815.1"], "publish")

    def test_never_publish_policy_does_not_depend_on_the_live_catalog(self):
        campaign = benchmark.load_manifest(
            ROOT / ".github" / "benchmarks" / "large-genomes-2026.json"
        )

        actions = {
            row["accession"]: row["publication"]
            for row in benchmark.plan_campaign(campaign, {"flat": []})
        }

        self.assertEqual(actions["GCA_000404065.3"], "skip-policy")
        self.assertEqual(actions["GCA_016271365.2"], "skip-policy")

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
        self.assertEqual(payload["job_id"], "large-genomes-2026-02-12345")
        self.assertFalse(payload["extra"]["publish_to_index"])

    def test_payload_cli_can_force_a_benchmark_only_nonpublishing_run(self):
        catalog = {"flat": []}
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
                    "GCA_054660815.1",
                    "--run-token",
                    "rerun",
                    "--no-publish",
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)["client_payload"]
        self.assertFalse(payload["extra"]["publish_to_index"])
        self.assertEqual(payload["job_id"], "large-genomes-2026-01-rerun")

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
        self.assertEqual(len(matrix["include"]), 20)
        self.assertEqual(matrix["include"][0]["accession"], "GCA_054660815.1")
        self.assertEqual(matrix["include"][1]["accession"], "GCA_000404065.3")
        self.assertEqual(matrix["include"][-1]["accession"], "GCA_963277665.1")
        self.assertEqual(matrix["include"][-1]["order"], 20)

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

        self.assertEqual(len(summary), 20)
        by_accession = {row["accession"]: row for row in summary}
        self.assertTrue(by_accession["GCA_000404065.3"]["build_complete"])
        self.assertEqual(
            by_accession["GCA_000404065.3"]["elapsed_seconds"], 2100
        )
        self.assertFalse(by_accession["GCA_963277665.1"]["report_available"])

    def test_summarize_cli_writes_json_csv_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            report_dir = tmp / "reports" / "one"
            report_dir.mkdir(parents=True)
            (report_dir / "build-report.json").write_text(
                json.dumps(
                    {
                        "benchmark": {"accession": "GCA_054660815.1"},
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
            self.assertIn("GCA_054660815.1", markdown)
            self.assertIn("8 min 20 s", markdown)


class WorkflowRuntimeContractTests(unittest.TestCase):
    def test_github_actions_use_node24_releases(self):
        workflows = "\n".join(
            path.read_text()
            for path in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        )

        self.assertNotIn("actions/checkout@v4", workflows)
        self.assertNotIn("actions/upload-artifact@v4", workflows)
        self.assertIn("actions/checkout@v7", workflows)
        self.assertIn("actions/upload-artifact@v7", workflows)

    def test_workflow_records_fine_grained_stage_timings(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()

        self.assertIn("- name: Resolve NCBI source", workflow)
        for metric in (
            "timings_sec.ncbi_resolve",
            "timings_sec.ncbi_stream_to_2bit",
            "timings_cpu_sec.ncbi_stream_python",
            "timings_cpu_sec.ncbi_stream_converter",
            "timings_sec.seed_generation",
            "timings_sec.package_compression",
            "timings_sec.storage_selection",
        ):
            self.assertIn(metric, workflow)

    def test_workflow_preserves_the_benchmark_publication_reason(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()

        self.assertIn("benchmark_publication_action", workflow)
        self.assertIn(
            "benchmark.publication_action \"${{ steps.params.outputs.benchmark_publication_action }}\"",
            workflow,
        )
        self.assertIn(
            "PUBLICATION_ACTION: ${{ steps.params.outputs.benchmark_publication_action }}",
            workflow,
        )

    def test_archive_validation_hashes_and_lists_one_tee_stream(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()

        self.assertIn(
            'scripts/validate_package_archive.sh "$TARBALL" "$PACKAGE"',
            workflow,
        )
        self.assertNotIn('tar -tzf "$TARBALL"', workflow)
        self.assertNotIn('sha256sum "$TARBALL"', workflow)
        self.assertNotIn('sha256sum "${TARBALL}"', workflow)

    def test_ncbi_build_streams_official_gzip_to_2bit_with_fallback(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()

        self.assertIn("- name: Stream NCBI FASTA to 2bit", workflow)
        self.assertIn("scripts/resolve_ncbi_fasta.py", workflow)
        self.assertIn("scripts/stream_fasta_to_2bit.py", workflow)
        self.assertIn("ncbi-ftp-stream", workflow)
        self.assertIn("ncbi-datasets-fallback", workflow)
        self.assertIn("datasets download genome accession", workflow)
        self.assertIn(
            "if: steps.params.outputs.fasta_source != 'ncbi'",
            workflow,
        )

    def test_builder_streams_every_non_ncbi_source_directly_to_2bit(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()

        self.assertIn(
            "- name: Stream Ensembl, URL, or uploaded FASTA to 2bit",
            workflow,
        )
        self.assertEqual(workflow.count("scripts/stream_fasta_to_2bit.py"), 2)
        self.assertIn('--source "$FASTA_SOURCE"', workflow)
        self.assertIn("--compression auto", workflow)
        self.assertIn("timings_sec.fasta_stream_to_2bit", workflow)
        self.assertIn('CONVERTER_STATUS" = "75', workflow)
        self.assertIn("benchmark-report/fasta-inspection.json", workflow)
        self.assertNotIn("- name: Download FASTA from Ensembl", workflow)
        self.assertNotIn("- name: Download FASTA from URL", workflow)
        self.assertNotIn("- name: Download uploaded FASTA", workflow)
        self.assertNotIn("- name: Inspect FASTA and collect stats", workflow)
        self.assertNotIn("- name: Convert FASTA to 2bit", workflow)
        self.assertNotIn("Validate nucleotide FASTA", workflow)
        self.assertNotIn("Extract FASTA headers and stats", workflow)
        self.assertNotIn("scripts/validate_fasta.py", workflow)
        self.assertNotIn("gzip -t downloaded.fasta", workflow)

        stream_start = workflow.index(
            "- name: Stream Ensembl, URL, or uploaded FASTA to 2bit"
        )
        stream_end = workflow.index("- name: Expose FASTA metadata", stream_start)
        stream_step = workflow[stream_start:stream_end]
        self.assertNotIn("genome.fa", stream_step)
        self.assertIn('curl -fsS -X DELETE "$FASTA_UPLOAD_URL"', stream_step)

    def test_builder_has_no_circular_detection_network_stage(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()

        self.assertNotIn("Detect circular sequences", workflow)
        self.assertNotIn("detect_circular_sequences.py", workflow)
        self.assertNotIn("sequence_report.jsonl", workflow)
        self.assertNotIn("nuccore", workflow.lower())
        self.assertIn("circ_seqs: character(0)", workflow)

    def test_web_build_forms_do_not_request_or_display_circular_metadata(self):
        paths = [
            ROOT / "web" / "src" / "features" / "build" / "BuildPage.tsx",
            ROOT / "web" / "src" / "features" / "build" / "BatchMode.tsx",
            ROOT / "web" / "src" / "lib" / "ncbi.ts",
            ROOT / "web" / "src" / "lib" / "ensembl.ts",
        ]

        for path in paths:
            with self.subTest(path=path.name):
                contents = path.read_text()
                self.assertNotIn("circSeqs", contents)
                self.assertNotIn("circ_seqs", contents)
                self.assertNotIn("fetchCircularSequences", contents)
                self.assertNotIn("detectCircularFromKaryotype", contents)

    def test_api_and_dispatch_payloads_do_not_forward_circular_metadata(self):
        paths = [
            ROOT / "worker" / "src" / "index.ts",
            ROOT / ".github" / "workflows" / "batch-build.yml",
            ROOT / "scripts" / "large_genome_benchmark.py",
        ]

        for path in paths:
            with self.subTest(path=path.name):
                self.assertNotIn("circ_seqs", path.read_text())

    def test_benchmark_tarball_is_deleted_after_the_report_is_finalized(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()

        report_position = workflow.index("- name: Finalize benchmark report")
        cleanup_position = workflow.index("- name: Remove benchmark package artifact")
        upload_position = workflow.index("- name: Upload benchmark report")
        self.assertLess(report_position, cleanup_position)
        self.assertLess(cleanup_position, upload_position)
        cleanup = workflow[cleanup_position:upload_position]
        self.assertIn("steps.params.outputs.benchmark_mode == 'true'", cleanup)
        self.assertIn('rm -f -- "$TARBALL"', cleanup)

    def test_builder_steps_run_under_bash(self):
        workflow = (
            ROOT / ".github" / "workflows" / "build-bsgenome.yml"
        ).read_text()
        build_job_header = workflow.split("\n    steps:", 1)[0]

        self.assertIn(
            "    defaults:\n      run:\n        shell: bash\n",
            build_job_header,
        )

    def test_bash_workflows_do_not_truncate_pipelines_with_head(self):
        workflow_paths = [
            ROOT / ".github" / "workflows" / "build-bsgenome.yml",
            ROOT
            / ".github"
            / "workflows"
            / "run-large-genome-benchmark-item.yml",
        ]

        for path in workflow_paths:
            with self.subTest(workflow=path.name):
                self.assertNotRegex(path.read_text(), r"\|\s*head(?:\s|$)")


if __name__ == "__main__":
    unittest.main()
