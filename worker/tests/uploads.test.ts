import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";

import worker from "../src/index.ts";

const MAX_BYTES = 4 * 1024 ** 3;
const PART_BYTES = 64 * 1024 ** 2;

function uploadFixture(t: TestContext, declaredSize = 12) {
  let storedSize = declaredSize;
  let deleted = false;
  const bucket = {
    async createMultipartUpload() { return { uploadId: "test-r2-upload" }; },
    resumeMultipartUpload() {
      return {
        async uploadPart(partNumber: number, body: ReadableStream) {
          await new Response(body).arrayBuffer();
          return { partNumber, etag: `etag-${partNumber}` };
        },
        async complete() {
          return { size: storedSize, customMetadata: { declared_size: String(declaredSize) } };
        },
        async abort() {},
      };
    },
    async head() {
      return { size: storedSize, customMetadata: { declared_size: String(declaredSize) } };
    },
    async delete() { deleted = true; },
  };
  const env = {
    GITHUB_PAT: "test-token",
    GITHUB_REPO: "example/repo",
    ALLOWED_ORIGIN: "https://autobsgenome.org",
    FASTA_UPLOADS: bucket,
  };
  t.mock.method(globalThis, "fetch", async (input: unknown) => {
    if (String(input).includes("/actions/workflows/")) {
      return Response.json({ total_count: 0, workflow_runs: [] });
    }
    if (String(input).endsWith("/dispatches")) return new Response(null, { status: 204 });
    throw new Error(`Unexpected request: ${input}`);
  });
  return {
    setStoredSize(size: number) { storedSize = size; },
    wasDeleted() { return deleted; },
    async request(url: string, method: string, body?: unknown, headers = {}) {
      return worker.fetch(new Request(url, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
        headers,
      }), env);
    },
    async create() {
      const response = await worker.fetch(new Request("https://api.autobsgenome.org/api/uploads", {
        method: "POST",
        body: JSON.stringify({ file_name: "test.fa", file_size: declaredSize }),
      }), env);
      assert.equal(response.status, 200);
      return response.json() as Promise<Record<string, string>>;
    },
  };
}

test("new upload tokens bind the file size and cannot be downgraded", async (t) => {
  const fixture = uploadFixture(t);
  const session = await fixture.create();
  const url = new URL(session.part_url_template.replace("{part_number}", "1"));
  assert.equal(url.searchParams.get("size"), "12");
  for (const replacement of ["13", null]) {
    if (replacement === null) url.searchParams.delete("size");
    else url.searchParams.set("size", replacement);
    const response = await fixture.request(url.toString(), "PUT", "sequence", { "Content-Length": "12" });
    assert.equal(response.status, 403);
  }
});

test("upload parts stay within the signed count and byte size", async (t) => {
  const fixture = uploadFixture(t);
  const session = await fixture.create();
  const extra = await fixture.request(session.part_url_template.replace("{part_number}", "2"), "PUT", "x", { "Content-Length": "12" });
  assert.equal(extra.status, 400);
  const wrongSize = await fixture.request(session.part_url_template.replace("{part_number}", "1"), "PUT", "x", { "Content-Length": "13" });
  assert.equal(wrongSize.status, 400);
});

test("completion rejects missing or duplicate parts before finalizing", async (t) => {
  const fixture = uploadFixture(t, PART_BYTES + 12);
  const session = await fixture.create();
  for (const parts of [
    [{ part_number: 1, etag: "a" }],
    [{ part_number: 1, etag: "a" }, { part_number: 1, etag: "a" }],
  ]) {
    const response = await fixture.request(session.complete_url, "POST", { parts });
    assert.equal(response.status, 400);
  }
});

for (const [size, expectedStatus] of [[13, 400], [MAX_BYTES + 1, 413]]) {
  test(`completion deletes an invalid ${size}-byte object`, async (t) => {
    const fixture = uploadFixture(t);
    const session = await fixture.create();
    fixture.setStoredSize(size);
    const response = await fixture.request(session.complete_url, "POST", { parts: [{ part_number: 1, etag: "a" }] });
    assert.equal(response.status, expectedStatus);
    assert.equal(fixture.wasDeleted(), true);
  });
}

test("a correctly completed upload can start a build", async (t) => {
  const fixture = uploadFixture(t);
  const session = await fixture.create();
  const part = await fixture.request(session.part_url_template.replace("{part_number}", "1"), "PUT", "ACGTACGTAA");
  assert.equal(part.status, 200);
  const response = await fixture.request(session.complete_url, "POST", { parts: [{ part_number: 1, etag: "a" }] });
  assert.equal(response.status, 200);
  const build = await fixture.request("https://api.autobsgenome.org/api/build", "POST", {
    package_name: "BSgenome.Test.Upload.One", organism: "Test organism",
    fasta_source: "upload", fasta_upload_url: session.download_url,
  });
  assert.equal(build.status, 200);
});

test("build submission rejects an oversized stored upload", async (t) => {
  const fixture = uploadFixture(t);
  const session = await fixture.create();
  fixture.setStoredSize(MAX_BYTES + 1);
  const response = await fixture.request("https://api.autobsgenome.org/api/build", "POST", {
    package_name: "BSgenome.Test.Upload.One", organism: "Test organism",
    fasta_source: "upload", fasta_upload_url: session.download_url,
  });
  assert.equal(response.status, 413);
});

test("existing signed upload URLs can still complete and dispatch", async (t) => {
  const fixture = uploadFixture(t);
  const session = await fixture.create();
  const url = new URL(session.download_url);
  url.searchParams.delete("size");
  const value = [session.upload_id, "test.fa", url.searchParams.get("exp"), session.r2_upload_id].join(":");
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode("test-token"), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value));
  url.searchParams.set("token", Buffer.from(signature).toString("hex"));
  const complete = new URL(url);
  complete.pathname += "/complete";
  const response = await fixture.request(complete.toString(), "POST", { parts: [{ part_number: 1, etag: "a" }] });
  assert.equal(response.status, 200);
  const build = await fixture.request("https://api.autobsgenome.org/api/build", "POST", {
    package_name: "BSgenome.Test.Upload.One", organism: "Test organism",
    fasta_source: "upload", fasta_upload_url: url.toString(),
  });
  assert.equal(build.status, 200);
});
