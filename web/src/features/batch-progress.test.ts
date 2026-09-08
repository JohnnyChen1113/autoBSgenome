import assert from "node:assert/strict";
import test from "node:test";
import { summarizeBatchProgress } from "./build/batch-progress.ts";

test("a failed build counts as finished and allows batch results", () => {
  assert.deepEqual(summarizeBatchProgress([
    { status: "done" }, { status: "failed" }, { status: "error" },
  ]), { total: 2, done: 1, failed: 1, finished: 2, building: 0, allFinished: true });
});

test("input errors do not finish a batch while a build is still running", () => {
  const result = summarizeBatchProgress([
    { status: "done" }, { status: "building" }, { status: "error" },
  ]);
  assert.equal(result.allFinished, false);
  assert.equal(result.finished, 1);
  assert.equal(result.total, 2);
});

test("an undispatched ready item keeps batch results pending", () => {
  assert.equal(summarizeBatchProgress([{ status: "done" }, { status: "ready" }]).allFinished, false);
  assert.equal(summarizeBatchProgress([{ status: "error" }]).allFinished, false);
});
