import assert from "node:assert/strict";
import test from "node:test";

import {
  buildRetentionMessage,
  formatScheduledCleanupAfter,
} from "./build-retention.ts";

test("retention notice distinguishes the hosted download and tells users to save it", () => {
  assert.equal(
    buildRetentionMessage(2),
    "The server-hosted .tar.gz download is public and scheduled for automatic cleanup approximately 2 days after build completion. Download and keep a local copy if you need it later."
  );
});

test("cleanup deadline is formatted as an unambiguous UTC time", () => {
  assert.equal(
    formatScheduledCleanupAfter("2026-08-23T12:00:00.000Z"),
    "2026-08-23 12:00 UTC"
  );
});
