// Homepage marketing facts must match what the feature actually does — `npm test`.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { Catalog } from "../lib/lifestyle/types.ts";
import { LIFESTYLE_FACTS, LIFESTYLE_PATH } from "../lib/lifestyle/marketing.ts";

const catalog: Catalog = JSON.parse(
  readFileSync(new URL("./fixtures/lifestyle-catalog.json", import.meta.url), "utf-8"),
);

test("homepage facts match the real catalog", () => {
  assert.equal(LIFESTYLE_FACTS.areas, catalog.region_count);
  assert.equal(LIFESTYLE_FACTS.factors, catalog.attributes.length);
  assert.equal(LIFESTYLE_FACTS.sources, catalog.sources.length);
  assert.equal(LIFESTYLE_FACTS.presets, catalog.presets.length);
  assert.ok(catalog.attributes.every((a) => a.available), "every advertised factor has data");
});

test("entry points link to the questionnaire", () => {
  assert.equal(LIFESTYLE_PATH, "/lifestyle");
  for (const file of ["../components/lifestyle/LifestyleEntryBar.tsx", "../components/lifestyle/LifestyleFeatureCard.tsx"]) {
    const src = readFileSync(new URL(file, import.meta.url), "utf-8");
    assert.match(src, /href=\{LIFESTYLE_PATH\}/, file);
  }
});
