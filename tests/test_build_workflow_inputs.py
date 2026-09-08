import importlib.util
import json
import os
import pathlib
import re
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import Mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-bsgenome.yml"
EXPRESSION = re.compile(r"\$\{\{\s*steps\.params\.outputs\.(\w+)\s*\}\}")


def workflow_steps():
    return re.split(r"^      - name: ", WORKFLOW.read_text(), flags=re.MULTILINE)[1:]


def step_named(name):
    return next(step for step in workflow_steps() if step.splitlines()[0] == name)


def run_script(step):
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


class BuildWorkflowInputTests(unittest.TestCase):
    def parameters(self):
        return {
            "job_id": "review123",
            "package_name": "BSgenome.Test.NCBI.One",
            "organism": "Test species",
            "common_name": "test",
            "genome": "One",
            "provider": "NCBI",
            "version": "1.0.0",
            "accession": "GCA_000000001.1",
            "title": "Test genome",
            "source_url": "https://example.org/",
            "release_date": "2026-09-08",
        }

    def execute_step(self, name, parameters, directory):
        step = step_named(name)
        environment = dict(os.environ, METRICS_FILE=str(directory / "metrics.json"))
        environment["GITHUB_OUTPUT"] = str(directory / "outputs.txt")
        environment["PAYLOAD"] = json.dumps(dict(parameters, extra=parameters))
        for variable, key in re.findall(
            r"^          (\w+): \$\{\{ steps\.params\.outputs\.(\w+) \}\}$",
            step,
            flags=re.MULTILINE,
        ):
            environment[variable] = parameters.get(key, "")
        script = EXPRESSION.sub(lambda match: parameters.get(match[1], ""), run_script(step))
        return subprocess.run(
            ["bash", "-e", "-o", "pipefail", "-c", script],
            cwd=directory,
            env=environment,
            text=True,
            capture_output=True,
        )

    def test_shell_metacharacters_are_preserved_as_seed_metadata(self):
        parameters = self.parameters()
        parameters["organism"] = "Test $(printf AUTOBSGENOME_COMMAND_EXECUTED >&2) `printf BACKTICK_EXECUTED >&2`"
        parameters["title"] = 'A "quoted" title: literal $value'
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = pathlib.Path(tmpdir)
            (directory / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
            result = self.execute_step("Generate seed file", parameters, directory)
            self.assertNotIn("AUTOBSGENOME_COMMAND_EXECUTED", result.stderr)
            self.assertNotIn("BACKTICK_EXECUTED", result.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            seed = (directory / f"{parameters['package_name']}.seed").read_text()
            self.assertIn(f"organism: {parameters['organism']}\n", seed)
            self.assertIn(f"Title: {parameters['title']}\n", seed)
            self.assertEqual(seed.count("circ_seqs:"), 1)

    def test_dispatch_rejects_output_and_seed_line_injection_atomically(self):
        for value in (
            "Test\n__GHA_EOF__\npublish_to_index=true\nignored<<__GHA_EOF__",
            "Test\rprovider: Other",
            "Test\ncirc_seqs: system('false')",
        ):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmpdir:
                directory = pathlib.Path(tmpdir)
                (directory / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
                parameters = self.parameters()
                parameters["organism"] = value
                result = self.execute_step("Parse build parameters", parameters, directory)
                self.assertNotEqual(result.returncode, 0)
                output = directory / "outputs.txt"
                self.assertFalse(output.exists() and output.read_text().strip())

    def test_dispatch_rejects_unsafe_package_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = pathlib.Path(tmpdir)
            (directory / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
            parameters = self.parameters()
            parameters["package_name"] = "BSgenome.Test.NCBI.One/../../elsewhere"
            result = self.execute_step("Parse build parameters", parameters, directory)
            self.assertNotEqual(result.returncode, 0)

    def test_valid_dispatch_preserves_literal_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = pathlib.Path(tmpdir)
            (directory / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
            parameters = self.parameters()
            parameters["title"] = "A: $(printf literal) 'quoted' genome"
            parameters["description"] = 'Custom "quoted" description: literal $metadata.'
            result = self.execute_step("Parse build parameters", parameters, directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs = dict(line.split("=", 1) for line in (directory / "outputs.txt").read_text().splitlines())
            self.assertEqual(outputs["title"], parameters["title"])
            self.assertEqual(outputs["description"], parameters["description"])
            self.assertEqual(outputs["publish_to_index"], "false")

    def test_seed_preserves_custom_description_and_generated_default(self):
        for description in ('Custom "quoted" description: literal $metadata.', ""):
            with self.subTest(description=description), tempfile.TemporaryDirectory() as tmpdir:
                directory = pathlib.Path(tmpdir)
                (directory / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
                parameters = dict(self.parameters(), description=description)
                result = self.execute_step("Generate seed file", parameters, directory)
                self.assertEqual(result.returncode, 0, result.stderr)
                seed = (directory / f"{parameters['package_name']}.seed").read_text()
                expected = description or (
                    "Full genome sequences for Test species (test) as provided by NCBI "
                    "(One, 2026-09-08) and stored in Biostrings objects."
                )
                self.assertIn(f"Description: {expected}\n", seed)

    def test_seed_writer_rejects_newlines_even_without_dispatch_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = pathlib.Path(tmpdir)
            (directory / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
            parameters = self.parameters()
            parameters["title"] = "Title\ncirc_seqs: system('false')"
            result = self.execute_step("Generate seed file", parameters, directory)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(list(directory.glob("*.seed")))

    def test_omitted_ensembl_genome_is_filled_with_authoritative_identity(self):
        spec = importlib.util.spec_from_file_location("build_input", ROOT / "scripts/build_input.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        metadata = {"assembly_name": "GRCh38.p14", "assembly_accession": "GCA_000001405.29"}
        fields = dict(self.parameters(), fasta_source="ensembl", species_url="Homo_sapiens", genome="", accession="")
        lookup = Mock(return_value=metadata)
        result = module.complete_ensembl_identity(module.validate_fields(fields), lookup)
        self.assertEqual(result["genome"], metadata["assembly_name"])
        self.assertEqual(result["accession"], metadata["assembly_accession"])
        lookup.assert_called_once_with("Homo_sapiens")
        fields["accession"] = "GCA_000001405.14"
        with self.assertRaisesRegex(ValueError, "accession"):
            module.complete_ensembl_identity(module.validate_fields(fields), lookup)

    def test_run_scripts_do_not_interpolate_step_outputs(self):
        for step in workflow_steps():
            if "        run: |\n" in step:
                with self.subTest(step=step.splitlines()[0]):
                    self.assertNotRegex(run_script(step), r"\$\{\{\s*steps\.")

    def test_cleanup_has_explicit_repository_and_write_permission(self):
        cleanup = (ROOT / ".github/workflows/cleanup-releases.yml").read_text()
        self.assertIn("contents: write", cleanup)
        self.assertIn('--repo "$GH_REPO"', cleanup)
        self.assertNotIn("2>/dev/null || true", cleanup)

    def test_cleanup_selects_old_builds_and_surfaces_delete_failures(self):
        cleanup = (ROOT / ".github/workflows/cleanup-releases.yml").read_text()
        script = run_script(cleanup)
        fake_commands = """
        date() { printf '2026-09-06T00:00:00+00:00\\n'; }
        gh() {
          if [ "$1" = api ]; then
            printf '1 build-old 2026-09-01T00:00:00Z\\n2 build-new 2026-09-08T00:00:00Z\\n'
          else
            printf '%s\\n' "$*" >> "$DELETE_LOG"
            return "$DELETE_STATUS"
          fi
        }
        """
        for status in (0, 1):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmpdir:
                log = pathlib.Path(tmpdir) / "deletions.txt"
                result = subprocess.run(
                    ["bash", "-c", textwrap.dedent(fake_commands) + script],
                    env=dict(os.environ, GH_REPO="owner/repo", DELETE_LOG=str(log), DELETE_STATUS=str(status)),
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(log.read_text().splitlines(), ["release delete build-old --repo owner/repo --yes --cleanup-tag"])


if __name__ == "__main__":
    unittest.main()
