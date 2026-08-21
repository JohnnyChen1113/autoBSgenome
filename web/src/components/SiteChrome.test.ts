import assert from "node:assert/strict";
import test from "node:test";

import { SITE_NAV_ITEMS } from "./site-navigation.ts";

test("site navigation exposes a labeled Home link", () => {
  assert.ok(
    SITE_NAV_ITEMS.some(
      (item) => item.href === "/" && item.label === "Home" && item.key === "home"
    )
  );
});
