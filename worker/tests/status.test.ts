import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";

import worker from "../src/index.ts";

const env = {
  GITHUB_PAT: "test-token",
  GITHUB_REPO: "example/repo",
  ALLOWED_ORIGIN: "https://autobsgenome.org",
};

async function statusFor(
  t: TestContext,
  { conclusion = null, completed = false, old = false, release = null }: {
    conclusion?: string | null;
    completed?: boolean;
    old?: boolean;
    release?: Record<string, unknown> | null;
  }
) {
  const updatedAt = new Date(Date.now() - (old ? 3 * 86400000 : 1000)).toISOString();
  t.mock.method(globalThis, "fetch", async (input: unknown) => {
    const url = String(input);
    if (url.includes("/releases/tags/")) {
      return release ? Response.json(release) : new Response(null, { status: 404 });
    }
    if (url.includes("/actions/workflows/")) {
      return Response.json({ workflow_runs: [{
        id: 123,
        status: completed ? "completed" : "in_progress",
        conclusion,
        created_at: updatedAt,
        run_started_at: updatedAt,
        updated_at: updatedAt,
        display_title: "[job deadbeef] Build BSgenome.Test.NCBI.One",
      }] });
    }
    if (url.includes("/actions/runs/123/jobs")) {
      return Response.json({ jobs: [] });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  const response = await worker.fetch(
    new Request("https://api.autobsgenome.org/api/status/deadbeef"), env
  );
  assert.equal(response.status, 200);
  return response.json() as Promise<Record<string, unknown>>;
}

for (const conclusion of ["cancelled", "timed_out", "failure"]) {
  test(`a ${conclusion} workflow is terminal without a failure release`, async (t) => {
    const body = await statusFor(t, { completed: true, conclusion });
    assert.equal(body.status, "failed");
    assert.equal(body.workflow_conclusion, conclusion);
    assert.ok(body.message);
  });
}

test("a cleaned-up successful build reports an expired download", async (t) => {
  const body = await statusFor(t, { completed: true, conclusion: "success", old: true });
  assert.equal(body.status, "failed");
  assert.equal(body.reason, "expired");
  assert.match(String(body.message), /expired/i);
});

test("a recently finished build without a download is terminal", async (t) => {
  const body = await statusFor(t, { completed: true, conclusion: "success" });
  assert.equal(body.status, "failed");
  assert.notEqual(body.reason, "expired");
});

const asset = {
  name: "BSgenome.Test.NCBI.One_1.0.0.tar.gz",
  browser_download_url: "https://github.com/example/repo/releases/download/build-deadbeef/BSgenome.Test.NCBI.One_1.0.0.tar.gz",
  size: 123,
  state: "uploaded",
};
const release = {
  name: "BSgenome.Test.NCBI.One 1.0.0",
  body: "Build complete",
  created_at: new Date().toISOString(),
  draft: false,
};

for (const [name, fields] of [
  ["no assets", { assets: [] }],
  ["an unfinished upload", { assets: [{ ...asset, state: "starter", size: 0 }] }],
  ["a draft release", { draft: true, assets: [asset] }],
] as const) {
  test(`an active build with ${name} remains building`, async (t) => {
    const body = await statusFor(t, { release: { ...release, ...fields } });
    assert.equal(body.status, "building");
    assert.equal(body.download_url, undefined);
  });
}

test("download selection finds the tarball after an unrelated asset", async (t) => {
  const body = await statusFor(t, { release: {
    ...release,
    assets: [{ ...asset, name: "build-report.json" }, asset],
  } });
  assert.equal(body.status, "complete");
  assert.equal(body.file_name, asset.name);
  assert.equal(body.download_url, "https://packages.autobsgenome.org/build-deadbeef/BSgenome.Test.NCBI.One_1.0.0.tar.gz");
});
