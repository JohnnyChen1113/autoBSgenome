import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import autoBSgenome as cli


class SafeForgedLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("Rscript"):
            raise unittest.SkipTest("Rscript is not installed")
        result = subprocess.run(
            ["Rscript", "--vanilla", "-e", "quit(status=if(requireNamespace('BSgenomeForge', quietly=TRUE)) 0L else 1L)"],
            capture_output=True,
        )
        if result.returncode:
            raise unittest.SkipTest("BSgenomeForge is not installed")

    def test_real_forge_preserves_literal_template_tokens(self):
        with tempfile.TemporaryDirectory(prefix="forge  metadata ") as tmpdir:
            workspace = pathlib.Path(tmpdir)
            draft = cli.BuildDraft(
                package_name="BSgenome.Test.NCBI.One",
                organism="Test @GENOME@ species",
                common_name="Common @ORGANISM@ name",
                genome="Assembly @PROVIDER@",
                provider="NCBI",
                release_date="Sep. 2026",
                source_url="https://example.org/user@example.org/",
                title="Literal @PKGNAME@ title",
                description='Quoted "description" with @PKGTITLE@ and @UNKNOWN@ tokens.',
            ).generated()
            # Advanced forge copies this file; sequence reading is tested separately.
            (workspace / "genome.2bit").write_bytes(b"metadata-only forge fixture")
            seed = cli.write_seed(draft, workspace)
            original_seed = seed.read_bytes()
            forge_seed = cli.prepare_forge_seed(seed, workspace)
            result = subprocess.run(
                ["Rscript", "--vanilla", "-e",
                 "BSgenomeForge::forgeBSgenomeDataPkg(commandArgs(TRUE)[1])", str(forge_seed)],
                cwd=workspace, text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            cli.rewrite_forged_metadata(seed, workspace)
            self.assertEqual(seed.read_bytes(), original_seed)
            check = '''
            args <- commandArgs(TRUE)
            seed <- read.dcf(args[1])[1L, ]
            description <- read.dcf(args[2])[1L, ]
            for (name in c("Title", "Description", "organism", "common_name", "genome",
                           "provider", "release_date", "source_url"))
                stopifnot(identical(seed[[name]], description[[name]]))
            stopifnot(endsWith(description[["biocViews"]], seed[["organism_biocview"]]))
            '''
            result = subprocess.run(
                ["Rscript", "--vanilla", "-e", check, str(seed),
                 str(workspace / draft.package_name / "DESCRIPTION")],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_quotes_backslashes_and_placeholder_text_remain_literal_in_r(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = pathlib.Path(tmpdir)
            draft = cli.BuildDraft(
                package_name="BSgenome.Test.NCBI.One",
                organism='Test "quoted" \\path @GENOME@',
                genome='" + {message("R_TEMPLATE_EXECUTED"); 0} + "',
                provider='NCBI "quoted" \\provider',
                common_name='A "common" name',
                release_date="2026-09-08",
                source_url='https://example.org/"quoted"?literal=\\value',
                title=r'\Sexpr[stage=build]{assign("RD_TEMPLATE_EXECUTED", TRUE, envir=.GlobalEnv); "title"}',
                description=r'Original "quoted" description: \Sexpr[stage=build]{assign("RD_TEMPLATE_EXECUTED", TRUE, envir=.GlobalEnv); "text"} 100% {braces} @PKGTITLE@',
            ).generated()
            seed = cli.write_seed(draft, workspace)
            original_seed = seed.read_bytes()
            output = workspace / draft.package_name / "R" / "zzz.R"
            output.parent.mkdir(parents=True)
            output.write_text('stop("GENERATED_LOADER_MUST_NOT_EXECUTE")\n')

            rd = workspace / draft.package_name / "man" / "package.Rd"
            rd.parent.mkdir(parents=True)
            rd.write_text("placeholder\n")
            description = workspace / draft.package_name / "DESCRIPTION"
            description.write_text(
                f"Package: {draft.package_name}\nTitle: {draft.title}\n"
                f"Description: {draft.description.replace('@PKGTITLE@', 'incorrect nested substitution')}\nAuthor: Test author\n"
            )
            cli.rewrite_forged_metadata(seed, workspace)
            self.assertEqual(seed.read_bytes(), original_seed)
            check = r'''
            args <- commandArgs(trailingOnly=TRUE)
            metadata <- read.dcf(args[1])[1L, ]
            package_metadata <- read.dcf(args[4])[1L, ]
            stopifnot(identical(package_metadata[["Title"]], metadata[["Title"]]))
            stopifnot(identical(package_metadata[["Description"]], metadata[["Description"]]))
            source(args[2])
            captured <- NULL
            BSgenome <- function(...) { captured <<- list(...); captured }
            system.file <- function(...) "unused-test-directory"
            asNamespace <- function(...) new.env()
            namespaceExport <- function(...) invisible(NULL)
            .onLoad("unused", metadata[["Package"]])
            stopifnot(identical(captured$organism, metadata[["organism"]]))
            stopifnot(identical(captured$genome, metadata[["genome"]]))
            stopifnot(identical(captured$provider, metadata[["provider"]]))
            stopifnot(identical(captured$common_name, metadata[["common_name"]]))
            stopifnot(identical(captured$release_date, metadata[["release_date"]]))
            stopifnot(identical(captured$source_url, metadata[["source_url"]]))
            stopifnot(identical(captured$circ_seqs, character(0)))
            rd <- tools::parse_Rd(args[3])
            rd <- tools:::prepare_Rd(rd, stages="build")
            stopifnot(!exists("RD_TEMPLATE_EXECUTED", envir=.GlobalEnv, inherits=FALSE))
            rendered <- paste(capture.output(tools::Rd2txt(rd)), collapse="\n")
            stopifnot(grepl("RD_TEMPLATE_EXECUTED", rendered, fixed=TRUE))
            stopifnot(grepl("@PKGTITLE@", rendered, fixed=TRUE))
            '''
            check_path = workspace / "check.R"
            check_path.write_text(check)
            result = subprocess.run(
                ["Rscript", "--vanilla", str(check_path), str(seed), str(output), str(rd), str(description)],
                env=os.environ.copy(), text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("R_TEMPLATE_EXECUTED", result.stderr)
            self.assertNotIn("GENERATED_LOADER_MUST_NOT_EXECUTE", result.stderr)


if __name__ == "__main__":
    unittest.main()
