import gzip
import hashlib
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import autoBSgenome as cli


class SourceDetectionTests(unittest.TestCase):
    def test_detects_bare_ncbi_accession(self) -> None:
        source = cli.detect_source("GCF_000001405.40")
        self.assertIsNotNone(source)
        self.assertEqual(source.kind, "ncbi")
        self.assertEqual(source.accession, "GCF_000001405.40")

    def test_detects_ncbi_url(self) -> None:
        source = cli.detect_source(
            "https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_010015735.1/"
        )
        self.assertIsNotNone(source)
        self.assertEqual(source.kind, "ncbi")
        self.assertEqual(source.accession, "GCA_010015735.1")

    def test_detects_ensembl_genomes_url_and_full_slug(self) -> None:
        source = cli.detect_source(
            "https://fungi.ensembl.org/Aaosphaeria_arxii_cbs_175_79_gca_010015735/Info/Index"
        )
        self.assertIsNotNone(source)
        self.assertEqual(source.kind, "ensembl")
        self.assertEqual(source.group, "fungi")
        self.assertEqual(
            source.species,
            "aaosphaeria_arxii_cbs_175_79_gca_010015735",
        )

    def test_rejects_lookalike_ensembl_hostname(self) -> None:
        self.assertIsNone(
            cli.detect_source(
                "https://fungi.ensembl.org.evil.example/Homo_sapiens/Info/Index"
            )
        )

    def test_other_websites_use_manual_mode(self) -> None:
        self.assertIsNone(cli.detect_source("https://example.org/genome/GCF_000001405.40"))


class MetadataTests(unittest.TestCase):
    def test_release_date_comes_from_upstream_value(self) -> None:
        self.assertEqual(cli.format_release_date("2018-09-09"), "Sep. 2018")
        self.assertEqual(cli.BuildDraft().release_date, "")

    def test_package_name_matches_current_normalization(self) -> None:
        self.assertEqual(
            cli.build_package_name("Apis mellifera", "NCBI", "Amel_HAv3.1"),
            "BSgenome.Amellifera.NCBI.AmelHAv31",
        )

    def test_ncbi_response_prefills_editable_draft(self) -> None:
        report = {
            "reports": [
                {
                    "organism": {
                        "organism_name": "Apis mellifera",
                        "common_name": "honey bee",
                    },
                    "assembly_info": {
                        "assembly_name": "Amel_HAv3.1",
                        "release_date": "2018-09-09",
                    },
                }
            ]
        }
        def fake_request(url, **_kwargs):
            self.assertNotIn("sequence_reports", url)
            self.assertNotIn("nuccore", url)
            return report

        source = cli.SourceInput("ncbi", "GCF_003254395.2", accession="GCF_003254395.2")
        with patch.object(cli, "request_json", side_effect=fake_request):
            draft = cli.resolve_ncbi(source)
        self.assertEqual(draft.package_name, "BSgenome.Amellifera.NCBI.AmelHAv31")
        self.assertEqual(draft.release_date, "Sep. 2018")
        self.assertFalse(hasattr(draft, "circ_seqs"))

    def test_ensembl_response_uses_assembly_date_when_ncbi_is_unavailable(self) -> None:
        assembly = {
            "assembly_name": "Aaoar1",
            "assembly_accession": "GCA_010015735.1",
            "assembly_date": "2020-01-28",
            "karyotype": [],
        }
        genome = {
            "scientific_name": "Aaosphaeria arxii",
            "display_name": "CBS 175.79",
        }

        def fake_request(url, **_kwargs):
            if "/info/assembly/" in url:
                return assembly
            if "/info/genomes/" in url:
                return genome
            raise AssertionError(f"Unexpected request: {url}")

        source = cli.SourceInput(
            "ensembl",
            "https://fungi.ensembl.org/Aaosphaeria_arxii/Info/Index",
            species="aaosphaeria_arxii",
            group="fungi",
        )
        with patch.object(cli, "request_json", side_effect=fake_request):
            draft = cli.resolve_ensembl(source)
        self.assertEqual(draft.package_name, "BSgenome.Aarxii.Ensembl.Aaoar1")
        self.assertEqual(draft.release_date, "Jan. 2020")
        self.assertEqual(draft.ensembl_group, "fungi")
        self.assertEqual(draft.as_dict().get("ensembl_assembly"), "Aaoar1")

    def test_ensembl_patch_release_uses_authoritative_filename_identity(self) -> None:
        source = cli.SourceInput(
            "ensembl", "https://www.ensembl.org/Homo_sapiens/Info/Index",
            species="homo_sapiens", group="vertebrates",
        )
        assembly = {
            "assembly_name": "GRCh38.p14",
            "assembly_accession": "GCA_000001405.29",
            "default_coord_system_version": "GRCh38",
            "assembly_date": "2022-02-03",
        }
        with patch.object(cli, "request_json", side_effect=[assembly, {}]):
            draft = cli.resolve_ensembl(source)
        self.assertEqual(draft.genome, "GRCh38.p14")
        self.assertEqual(draft.ensembl_assembly, "GRCh38")
        with patch.object(cli, "_latest_ensembl_release", return_value=116), patch.object(
            cli, "request_text", return_value='<a href="Homo_sapiens.GRCh38.dna.toplevel.fa.gz">FASTA</a>'
        ):
            resolved = cli.resolve_ensembl_fasta(
                draft.ensembl_species, draft.ensembl_group, draft.accession,
                expected_assembly=draft.ensembl_assembly,
            )
        self.assertTrue(resolved.endswith("/Homo_sapiens.GRCh38.dna.toplevel.fa.gz"))

    def test_wizard_accepts_prefilled_values(self) -> None:
        draft = cli.BuildDraft(
            package_name="BSgenome.Amellifera.NCBI.AmelHAv31",
            organism="Apis mellifera",
            genome="Amel_HAv3.1",
            provider="NCBI",
            release_date="Sep. 2018",
        ).generated()
        with patch("builtins.input", return_value=""):
            result = cli.run_wizard(draft)
        self.assertEqual(result.package_name, draft.package_name)
        self.assertEqual(result.organism, "Apis mellifera")

    def test_wizard_reprompts_for_missing_required_metadata(self) -> None:
        required_values = {
            "title": "Honey bee genome",
            "description": "Full honey bee genome.",
            "version": "1.0.0",
            "organism": "Apis mellifera",
            "genome": "Amel_HAv3.1",
            "provider": "NCBI",
            "release_date": "Sep. 2018",
            "BSgenomeObjname": "Amellifera",
        }
        for missing, replacement in required_values.items():
            with self.subTest(field=missing):
                draft = cli.BuildDraft(
                    package_name="BSgenome.Amellifera.NCBI.AmelHAv31",
                    **required_values,
                )
                setattr(draft, missing, "")
                prompts = []

                def answer(prompt):
                    if prompt.startswith(f"{missing}:"):
                        prompts.append(prompt)
                        return "" if len(prompts) == 1 else replacement
                    return ""

                with patch("builtins.input", side_effect=answer), redirect_stdout(io.StringIO()):
                    result = cli.run_wizard(draft)
                self.assertEqual(getattr(result, missing), replacement)
                self.assertEqual(len(prompts), 2)

    def test_wizard_allows_empty_optional_metadata(self) -> None:
        draft = cli.BuildDraft(
            package_name="BSgenome.Amellifera.NCBI.AmelHAv31",
            title="Honey bee genome",
            description="Full honey bee genome.",
            organism="Apis mellifera",
            genome="Amel_HAv3.1",
            provider="NCBI",
            release_date="Sep. 2018",
            BSgenomeObjname="Amellifera",
        )
        with patch("builtins.input", return_value=""), redirect_stdout(io.StringIO()):
            result = cli.run_wizard(draft)
        self.assertEqual(result.common_name, "")
        self.assertEqual(result.source_url, "")
        self.assertEqual(result.organism_biocview, "")


class FastaAndSeedTests(unittest.TestCase):
    def test_truncated_local_gzip_reprompts_and_preserves_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "truncated.fa.gz"
            truncated = gzip.compress(b">chr1\nACGT\n")[:-8]
            source.write_bytes(truncated)
            valid = workspace / "valid.fa"
            valid.write_text(">chr2\nTGCA\n")
            with patch("builtins.input", side_effect=[str(source), str(valid)]), redirect_stdout(io.StringIO()):
                try:
                    fasta = cli.choose_fasta(cli.BuildDraft(), workspace)
                except EOFError as error:
                    self.fail(f"Truncated gzip must allow another local file: {error}")
            self.assertEqual(fasta.read_text(), ">chr2\nTGCA\n")
            self.assertEqual(source.read_bytes(), truncated)

    def test_truncated_gzip_does_not_leave_partial_fasta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "truncated.fa.gz"
            source.write_bytes(gzip.compress(b">chr1\n" + b"ACGT" * 50000 + b"\n")[:-8])
            destination = workspace / "genome.fa"
            try:
                cli._copy_or_decompress(source, destination)
            except cli.AutoBSgenomeError:
                pass
            except EOFError as error:
                self.fail(f"Expected a recoverable FASTA error: {error}")
            else:
                self.fail("Truncated gzip was accepted")
            self.assertFalse(destination.exists())
            self.assertEqual(list(workspace.glob("*.part")), [])

    def test_failed_decompression_preserves_existing_fasta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "truncated.fa.gz"
            source.write_bytes(gzip.compress(b">chr1\nACGT\n")[:-8])
            destination = workspace / "genome.fa"
            destination.write_text(">existing\nTGCA\n")
            with self.assertRaises(cli.AutoBSgenomeError):
                cli._copy_or_decompress(source, destination)
            self.assertEqual(destination.read_text(), ">existing\nTGCA\n")
            self.assertEqual(list(workspace.glob("*.part")), [])

    def test_truncated_official_gzip_offers_local_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            local = workspace / "local.fa"
            local.write_text(">local\nACGT\n")

            def fake_download(_url, destination, **_kwargs):
                destination.write_bytes(gzip.compress(b">broken\nACGT\n")[:-8])
                return destination

            draft = cli.BuildDraft(data_source="ensembl")
            draft.ensembl_assembly = "Example1"
            with patch.object(cli, "resolve_ensembl_fasta", return_value="https://ftp.ensembl.org/genome.fa.gz"), patch.object(
                cli, "download_file", side_effect=fake_download
            ), patch.object(cli, "request_text", return_value=""), patch(
                "builtins.input", side_effect=["1", "", str(local)]
            ), redirect_stdout(io.StringIO()):
                try:
                    fasta = cli.choose_fasta(draft, workspace)
                except EOFError as error:
                    self.fail(f"Truncated official gzip must offer local fallback: {error}")
            self.assertEqual(fasta.read_text(), ">local\nACGT\n")

    def test_ensembl_download_verifies_published_bsd_checksum(self) -> None:
        # Fixed gzip bytes and BSD sum independently checked with the system sum utility.
        payload = bytes.fromhex("1f8b08000000000002ffb34bce2832e47274760fe10200753aef2a0b000000")
        url = "https://ftp.ensembl.org/pub/release-116/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.toplevel.fa.gz"
        checksum_url = url.rsplit("/", 1)[0] + "/CHECKSUMS"

        def fake_download(_url, destination, **_kwargs):
            destination.write_bytes(payload)
            return destination

        draft = cli.BuildDraft(data_source="ensembl", ensembl_assembly="GRCh38")
        for checksum, blocks, expected_failure in [(43431, 1, False), (43430, 1, True), (43431, 2, True)]:
            with self.subTest(checksum=checksum, blocks=blocks), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory)
                checksums = f"{checksum} {blocks} Homo_sapiens.GRCh38.dna.toplevel.fa.gz\n"
                with patch.object(cli, "resolve_ensembl_fasta", return_value=url), patch.object(
                    cli, "download_file", side_effect=fake_download
                ), patch.object(cli, "request_text", return_value=checksums) as request, redirect_stdout(io.StringIO()):
                    if expected_failure:
                        with self.assertRaisesRegex(cli.AutoBSgenomeError, "checksum mismatch"):
                            cli.download_ensembl_fasta(draft, workspace)
                        self.assertFalse((workspace / "genome.fa").exists())
                    else:
                        fasta = cli.download_ensembl_fasta(draft, workspace)
                        self.assertEqual(fasta.read_text(), ">chr1\nACGT\n")
                        self.assertIsNotNone(request.call_args)
                        self.assertEqual(request.call_args.args[0], checksum_url)

    def test_ensembl_download_warns_when_optional_checksum_is_missing(self) -> None:
        payload = gzip.compress(b">chr1\nACGT\n")
        draft = cli.BuildDraft(data_source="ensembl", ensembl_assembly="GRCh38")

        def fake_download(_url, destination, **_kwargs):
            destination.write_bytes(payload)
            return destination

        for response in ["12345 1 another.fa.gz\n", cli.AutoBSgenomeError("CHECKSUMS unavailable")]:
            with self.subTest(response=str(response)), tempfile.TemporaryDirectory() as directory:
                output = io.StringIO()
                with patch.object(cli, "resolve_ensembl_fasta", return_value="https://ftp.ensembl.org/genome.fa.gz"), patch.object(
                    cli, "download_file", side_effect=fake_download
                ), patch.object(cli, "request_text", **(
                    {"side_effect": response} if isinstance(response, Exception) else {"return_value": response}
                )), redirect_stdout(output):
                    fasta = cli.download_ensembl_fasta(draft, Path(directory))
                self.assertEqual(fasta.read_text(), ">chr1\nACGT\n")
                self.assertIn("without checksum verification", output.getvalue())

    def test_bsd_checksum_counts_1024_byte_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload"
            path.write_bytes(bytes(range(256)) * 5)
            self.assertTrue(hasattr(cli, "_file_bsd_sum"))
            self.assertEqual(cli._file_bsd_sum(path), (2560, 2))

    def test_ensembl_download_rejects_fallback_with_different_assembly(self) -> None:
        draft = cli.BuildDraft(
            data_source="ensembl",
            genome="GRCh38",
            accession="GCA_000001405.15",
            ensembl_species="homo_sapiens",
            ensembl_group="vertebrates",
        )
        draft.ensembl_assembly = "GRCh38"

        def fake_listing(url, **_kwargs):
            if "/release-76/" in url:
                raise cli.AutoBSgenomeError("Latest release unavailable")
            return '<a href="Homo_sapiens.GRCh37.dna.toplevel.fa.gz">FASTA</a>'

        def fake_download(_url, destination, **_kwargs):
            destination.write_bytes(gzip.compress(b">chr1\nACGT\n"))
            return destination

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli, "_latest_ensembl_release", return_value=76), patch.object(
                cli, "request_text", side_effect=fake_listing
            ), patch.object(cli, "download_file", side_effect=fake_download), redirect_stdout(io.StringIO()):
                with self.assertRaises(cli.AutoBSgenomeError):
                    cli.download_ensembl_fasta(draft, Path(directory))

    def test_ensembl_download_matches_dotted_original_assembly_after_edit(self) -> None:
        source = cli.SourceInput(
            "ensembl", "https://metazoa.ensembl.org/Apis_mellifera/Info/Index",
            species="apis_mellifera", group="metazoa",
        )
        with patch.object(cli, "request_json", return_value={
            "assembly_name": "Amel_HAv3.1", "assembly_date": "2018-09-09"
        }):
            draft = cli.resolve_ensembl(source)
        draft.genome = "Edited package label"
        listing = '\n'.join([
            '<a href="Apis_mellifera.Amel_HAv3.10.dna.toplevel.fa.gz">Other assembly</a>',
            '<a href="Apis_mellifera.Amel_HAv3.1.dna.toplevel.fa.gz">Requested assembly</a>',
        ])

        def fake_download(_url, destination, **_kwargs):
            destination.write_bytes(gzip.compress(b">chr1\nACGT\n"))
            return destination

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli, "_latest_ensembl_release", return_value=63), patch.object(
                cli, "request_text", return_value=listing
            ), patch.object(cli, "download_file", side_effect=fake_download) as download, redirect_stdout(io.StringIO()):
                cli.download_ensembl_fasta(draft, Path(directory))
            self.assertTrue(download.call_args.args[0].endswith(
                "/Apis_mellifera.Amel_HAv3.1.dna.toplevel.fa.gz"
            ))

    def test_ensembl_download_requires_original_assembly_name(self) -> None:
        draft = cli.BuildDraft(
            data_source="ensembl", accession="GCA_000001405.15",
            genome="Editable label", ensembl_species="homo_sapiens",
            ensembl_group="vertebrates",
        )

        def fake_download(_url, destination, **_kwargs):
            destination.write_bytes(gzip.compress(b">chr1\nACGT\n"))
            return destination

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cli, "resolve_ensembl_fasta", return_value="https://ftp.ensembl.org/genome.fa.gz"), patch.object(
                cli, "download_file", side_effect=fake_download
            ), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(cli.AutoBSgenomeError, "assembly name"):
                    cli.download_ensembl_fasta(draft, Path(directory))

    def test_resolves_direct_ensembl_fasta_listing(self) -> None:
        def fake_json(url, **_kwargs):
            self.assertIn("/info/data/", url)
            return {"releases": [113]}

        def fake_text(url, **_kwargs):
            self.assertEqual(
                url,
                "https://ftp.ensembl.org/pub/release-113/fasta/apis_mellifera/dna/",
            )
            return '<a href="Apis_mellifera.Amel_HAv3.1.dna.toplevel.fa.gz">FASTA</a>'

        with patch.object(cli, "request_json", side_effect=fake_json), patch.object(
            cli, "request_text", side_effect=fake_text
        ):
            url = cli.resolve_ensembl_fasta(
                "apis_mellifera", "vertebrates", "GCA_003254395.2"
            )
        self.assertEqual(
            url,
            "https://ftp.ensembl.org/pub/release-113/fasta/apis_mellifera/dna/Apis_mellifera.Amel_HAv3.1.dna.toplevel.fa.gz",
        )

    def test_resolves_ncbi_genomic_fasta_without_selecting_cds(self) -> None:
        parent = (
            '<a href="GCF_003254395.2_Amel_HAv3.1/">assembly</a>'
        )
        assembly = "\n".join(
            [
                '<a href="GCF_003254395.2_Amel_HAv3.1_cds_from_genomic.fna.gz">cds</a>',
                '<a href="GCF_003254395.2_Amel_HAv3.1_genomic.fna.gz">genome</a>',
            ]
        )
        with patch.object(cli, "request_text", side_effect=[parent, assembly]):
            fasta_url, checksum_url = cli.resolve_ncbi_fasta_url(
                "GCF_003254395.2"
            )
        self.assertEqual(
            fasta_url,
            "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/003/254/395/GCF_003254395.2_Amel_HAv3.1/GCF_003254395.2_Amel_HAv3.1_genomic.fna.gz",
        )
        self.assertTrue(checksum_url.endswith("/md5checksums.txt"))

    def test_ncbi_download_verifies_md5_and_decompresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            payload = gzip.compress(b">chr1\nACGT\n")
            digest = hashlib.md5(payload).hexdigest()

            def fake_download(_url, destination, **_kwargs):
                destination.write_bytes(payload)
                return destination

            with patch.object(
                cli,
                "resolve_ncbi_fasta_url",
                return_value=(
                    "https://ftp.ncbi.nlm.nih.gov/example_genomic.fna.gz",
                    "https://ftp.ncbi.nlm.nih.gov/md5checksums.txt",
                ),
            ), patch.object(cli, "download_file", side_effect=fake_download), patch.object(
                cli,
                "request_text",
                return_value=f"{digest}  ./example_genomic.fna.gz\n",
            ):
                fasta = cli.download_ncbi_fasta("GCF_000001405.40", workspace)
            self.assertEqual(fasta.read_text(), ">chr1\nACGT\n")

    def test_seed_uses_confirmed_upstream_release_date(self) -> None:
        draft = cli.BuildDraft(
            package_name="BSgenome.Amellifera.NCBI.AmelHAv31",
            title="Honey bee genome",
            description="Full honey bee genome.",
            organism="Apis mellifera",
            common_name="honey bee",
            genome="Amel_HAv3.1",
            provider="NCBI",
            release_date="Sep. 2018",
            source_url="https://www.ncbi.nlm.nih.gov/datasets/genome/GCF_003254395.2/",
            organism_biocview="Apis_mellifera",
            BSgenomeObjname="Amellifera",
        )
        with tempfile.TemporaryDirectory() as directory:
            seed = cli.write_seed(draft, Path(directory))
            contents = seed.read_text()
        self.assertIn("release_date: Sep. 2018", contents)
        self.assertIn("circ_seqs: character(0)", contents)

if __name__ == "__main__":
    unittest.main()
