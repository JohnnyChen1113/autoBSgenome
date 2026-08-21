import assert from "node:assert/strict";
import test from "node:test";

import worker from "../src/index.ts";

test("completed build status declares the temporary download retention window", async () => {
  const originalFetch = globalThis.fetch;
  let requestCount = 0;

  globalThis.fetch = async () => {
    requestCount += 1;
    if (requestCount === 1) {
      return Response.json({
        name: "BSgenome.Hsapiens.NCBI.GRCh38 1.0.0",
        body: "Build complete",
        created_at: "2026-08-21T12:00:00Z",
        assets: [
          {
            name: "BSgenome.Hsapiens.NCBI.GRCh38_1.0.0.tar.gz",
            browser_download_url:
              "https://github.com/JohnnyChen1113/autoBSgenome/releases/download/build-testjob/BSgenome.Hsapiens.NCBI.GRCh38_1.0.0.tar.gz",
            size: 782000000,
          },
        ],
      });
    }
    throw new Error("Workflow progress is unavailable in this test");
  };

  try {
    const response = await worker.fetch(
      new Request("https://api.autobsgenome.org/api/status/testjob"),
      {
        GITHUB_PAT: "test-token",
        GITHUB_REPO: "JohnnyChen1113/autoBSgenome",
        ALLOWED_ORIGIN: "https://autobsgenome.org",
      }
    );
    const body = (await response.json()) as Record<string, unknown>;

    assert.equal(response.status, 200);
    assert.equal(body.status, "complete");
    assert.equal(body.retention_days, 2);
    assert.equal(body.scheduled_cleanup_after, "2026-08-23T12:00:00.000Z");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("new build response declares that its output is retained for two days", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("/actions/workflows/build-bsgenome.yml/runs")) {
      return Response.json({ workflow_runs: [] });
    }
    if (url.endsWith("/dispatches") && init?.method === "POST") {
      return new Response(null, { status: 204 });
    }
    throw new Error(`Unexpected request: ${url}`);
  };

  try {
    const response = await worker.fetch(
      new Request("https://api.autobsgenome.org/api/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          package_name: "BSgenome.Hsapiens.NCBI.GRCh38",
          organism: "Homo sapiens",
          accession: "GCF_000001405.40",
          data_source: "ncbi",
        }),
      }),
      {
        GITHUB_PAT: "test-token",
        GITHUB_REPO: "JohnnyChen1113/autoBSgenome",
        ALLOWED_ORIGIN: "https://autobsgenome.org",
      }
    );
    const body = (await response.json()) as Record<string, unknown>;

    assert.equal(response.status, 200);
    assert.equal(body.status, "queued");
    assert.equal(body.retention_days, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
