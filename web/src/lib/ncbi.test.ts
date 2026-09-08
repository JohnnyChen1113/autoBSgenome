import assert from "node:assert/strict";
import test from "node:test";
import { formatReleaseDate } from "./ncbi.ts";

test("assembly dates preserve the upstream calendar month in every timezone", () => {
  const timezone = process.env.TZ;
  process.env.TZ = "America/Los_Angeles";
  try {
    assert.equal(formatReleaseDate("2022-02-01"), "Feb. 2022");
    assert.equal(formatReleaseDate("2008-04"), "Apr. 2008");
    assert.equal(formatReleaseDate("2022-02-01T00:00:00Z"), "Feb. 2022");
    assert.equal(formatReleaseDate(""), "");
    assert.equal(formatReleaseDate("2022-13-01"), "");
  } finally {
    if (timezone === undefined) delete process.env.TZ;
    else process.env.TZ = timezone;
  }
});
