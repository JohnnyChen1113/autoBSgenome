import assert from "node:assert/strict";
import test from "node:test";

import worker from "../src/index.ts";


test("NCBI streaming is reported as one combined download-to-2bit step", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (input) => {
    const url = String(input);
    if (url.includes("/releases/tags/build-streamjob")) {
      return new Response(null, { status: 404 });
    }
    if (url.includes("/actions/workflows/build-bsgenome.yml/runs")) {
      return Response.json({
        workflow_runs: [
          {
            id: 123,
            status: "in_progress",
            conclusion: null,
            created_at: "2026-08-22T12:00:00Z",
            run_started_at: "2026-08-22T12:00:02Z",
            updated_at: "2026-08-22T12:00:10Z",
            display_title: "[job streamjob] Build BSgenome.Test.NCBI.One",
            html_url: "https://github.com/example/actions/runs/123",
          },
        ],
      });
    }
    if (url.includes("/actions/runs/123/jobs")) {
      return Response.json({
        jobs: [
          {
            name: "build",
            started_at: "2026-08-22T12:00:02Z",
            steps: [
              {
                name: "Stream NCBI FASTA to 2bit",
                status: "in_progress",
                conclusion: null,
                started_at: "2026-08-22T12:00:05Z",
                completed_at: null,
              },
            ],
          },
        ],
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  };

  try {
    const response = await worker.fetch(
      new Request("https://api.autobsgenome.org/api/status/streamjob"),
      {
        GITHUB_PAT: "test-token",
        GITHUB_REPO: "JohnnyChen1113/autoBSgenome",
        ALLOWED_ORIGIN: "https://autobsgenome.org",
      }
    );
    const body = (await response.json()) as {
      build_steps: Array<{ key: string; label: string; status: string }>;
    };

    const sequenceSteps = body.build_steps
      .filter((step) => ["download", "twobit"].includes(step.key))
      .map(({ key, label, status }) => ({ key, label, status }));
    assert.deepEqual(sequenceSteps, [
      {
        key: "twobit",
        label: "Streaming FASTA to 2bit",
        status: "running",
      },
    ]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("a skipped NCBI stream keeps separate download and conversion steps", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (input) => {
    const url = String(input);
    if (url.includes("/releases/tags/build-ensembljob")) {
      return new Response(null, { status: 404 });
    }
    if (url.includes("/actions/workflows/build-bsgenome.yml/runs")) {
      return Response.json({
        workflow_runs: [
          {
            id: 124,
            status: "in_progress",
            conclusion: null,
            created_at: "2026-08-22T12:00:00Z",
            run_started_at: "2026-08-22T12:00:02Z",
            updated_at: "2026-08-22T12:00:10Z",
            display_title: "[job ensembljob] Build BSgenome.Test.Ensembl.One",
            html_url: "https://github.com/example/actions/runs/124",
          },
        ],
      });
    }
    if (url.includes("/actions/runs/124/jobs")) {
      return Response.json({
        jobs: [
          {
            name: "build",
            started_at: "2026-08-22T12:00:02Z",
            steps: [
              {
                name: "Stream NCBI FASTA to 2bit",
                status: "completed",
                conclusion: "skipped",
                started_at: null,
                completed_at: "2026-08-22T12:00:03Z",
              },
              {
                name: "Download FASTA from Ensembl",
                status: "completed",
                conclusion: "success",
                started_at: "2026-08-22T12:00:03Z",
                completed_at: "2026-08-22T12:00:08Z",
              },
              {
                name: "Convert FASTA to 2bit",
                status: "in_progress",
                conclusion: null,
                started_at: "2026-08-22T12:00:08Z",
                completed_at: null,
              },
            ],
          },
        ],
      });
    }
    throw new Error(`Unexpected request: ${url}`);
  };

  try {
    const response = await worker.fetch(
      new Request("https://api.autobsgenome.org/api/status/ensembljob"),
      {
        GITHUB_PAT: "test-token",
        GITHUB_REPO: "JohnnyChen1113/autoBSgenome",
        ALLOWED_ORIGIN: "https://autobsgenome.org",
      }
    );
    const body = (await response.json()) as {
      build_steps: Array<{ key: string; label: string; status: string }>;
    };

    const sequenceSteps = body.build_steps
      .filter((step) => ["download", "twobit"].includes(step.key))
      .map(({ key, label, status }) => ({ key, label, status }));
    assert.deepEqual(sequenceSteps, [
      { key: "download", label: "Downloading FASTA", status: "complete" },
      { key: "twobit", label: "Converting to 2bit format", status: "running" },
    ]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
