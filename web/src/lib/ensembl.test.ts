import assert from "node:assert/strict";
import test from "node:test";

import { extractEnsemblSpecies, fetchEnsemblAssemblyInfo } from "./ensembl.ts";

test("Ensembl URLs preserve the complete strain and assembly slug", () => {
  assert.equal(
    extractEnsemblSpecies("https://fungi.ensembl.org/Aaosphaeria_arxii_cbs_175_79_gca_010015735/Info/Index"),
    "aaosphaeria_arxii_cbs_175_79_gca_010015735"
  );
  assert.equal(extractEnsemblSpecies("Mus_musculus_pwkphj"), "mus_musculus_pwkphj");
  assert.equal(extractEnsemblSpecies("https://plants.ensembl.org/arabidopsis_thaliana/Info/Index"), "arabidopsis_thaliana");
});

test("Ensembl input rejects lookalike hosts and unrelated paths", () => {
  assert.equal(extractEnsemblSpecies("https://notensembl.org/Homo_sapiens/Info/Index"), null);
  assert.equal(extractEnsemblSpecies("https://example.org/ensembl.org/Homo_sapiens"), null);
  assert.equal(extractEnsemblSpecies("GCA_000001405.29"), null);
});

test("optional Ensembl display metadata failure preserves the resolved assembly", async (t) => {
  t.mock.method(globalThis, "fetch", async (input: string | URL | Request) => {
    if (String(input).includes("/info/assembly/")) {
      return Response.json({ assembly_name: "TAIR10", assembly_accession: "GCA_000001735.1", assembly_date: "2008-04" });
    }
    throw new TypeError("Failed to fetch");
  });
  const info = await fetchEnsemblAssemblyInfo("arabidopsis_thaliana");
  assert.equal(info.assemblyName, "TAIR10");
  assert.equal(info.organism, "Arabidopsis thaliana");
  assert.equal(info.releaseDate, "Apr. 2008");
});
