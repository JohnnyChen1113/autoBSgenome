import assert from "node:assert/strict";
import test from "node:test";

import { fallbackBuildStepLabels } from "./build/build-progress.ts";


test("NCBI fallback progress names every observable long-running stage", () => {
  assert.deepEqual(fallbackBuildStepLabels("ncbi"), [
    "Queuing build on GitHub Actions",
    "Resolving NCBI source",
    "Streaming FASTA to 2bit",
    "Generating package metadata",
    "Forging BSgenome package",
    "Compressing package archive",
    "Validating package archive",
    "Uploading package release",
  ]);
});

test("custom URL fallback progress includes inspection before conversion", () => {
  assert.deepEqual(fallbackBuildStepLabels("url").slice(0, 4), [
    "Queuing build on GitHub Actions",
    "Downloading FASTA URL",
    "Inspecting FASTA metadata",
    "Converting to 2bit format",
  ]);
});
