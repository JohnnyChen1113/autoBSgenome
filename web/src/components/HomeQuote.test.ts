import assert from "node:assert/strict";
import test from "node:test";

import { HOME_QUOTE } from "./home-quote.ts";

test("home quote preserves the expert-afternoon contrast", () => {
  assert.equal(
    HOME_QUOTE,
    "Every BSgenome on Bioconductor took an expert and an afternoon to assemble. AutoBSgenome turns that into a paste-and-wait web service. Anyone, any genome, install-ready in minutes."
  );
});
