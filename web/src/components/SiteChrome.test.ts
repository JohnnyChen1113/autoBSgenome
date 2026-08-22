import assert from "node:assert/strict";
import test from "node:test";

import { SITE_FOOTER_CONTENT } from "./site-footer.ts";
import { SITE_NAV_ITEMS } from "./site-navigation.ts";

test("site navigation exposes a labeled Home link", () => {
  assert.ok(
    SITE_NAV_ITEMS.some(
      (item) => item.href === "/" && item.label === "Home" && item.key === "home"
    )
  );
});

test("site footer exposes the Lin Lab copyright and SLU identity", () => {
  assert.deepEqual(SITE_FOOTER_CONTENT, {
    copyright: {
      prefix: "Copyright © 2014-2026 ",
      lab: {
        label: "Lin Lab",
        href: "https://zlinlab.org/",
      },
      suffix: " - All rights reserved",
    },
    reportIssue: {
      label: "Report issue",
      href: "https://github.com/JohnnyChen1113/autoBSgenome/issues",
    },
    university: {
      href: "https://www.slu.edu",
      imageSrc: "/slu-logo.png",
      imageAlt: "Saint Louis University",
    },
  });
});
