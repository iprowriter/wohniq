// Lifestyle explorer helpers — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { compareRows, liveSummary, splitWeights, tripDetail } from "../lib/lifestyle/explorer.ts";
import type { RegionResult, WeightOut } from "../lib/lifestyle/types.ts";

const w = (attribute: string, value: number): WeightOut => ({ attribute, label: attribute, value, reasons: [], overridden: false });

function region(key: string, score: number, rent: number, minutes: number | null, green: number): RegionResult {
  return {
    rank: 1, key, name: key, district: "D", score, fits_budget: rent <= 700, warm_rent_eur: rent,
    within_commute: true, commute: minutes == null ? null : { destination: "tu", minutes, changes: 0, estimated: false },
    centroid: null, population: 1, headline: "", reasons: [], caveats: [], notes: [], evidence: [],
    factors: [{ attribute: "green", label: "Green", weight: 3, score: green, contribution: 0, raw: 0, unit: "", source_id: "s", year: "" }],
  };
}

describe("lifestyle explorer", () => {
  test("weights that count come first, the rest go behind '+N more'", () => {
    const { counted, rest } = splitWeights([w("quiet", 0), w("green", 3), w("cafes", 5), w("safety", 0)]);
    assert.deepEqual(counted.map((x) => x.attribute), ["cafes", "green"]);
    assert.deepEqual(rest.map((x) => x.attribute), ["quiet", "safety"]);
  });

  test("live summary counts areas that fit", () => {
    const scores = [
      { key: "a", rank: 1, score: 80, fits_budget: true, within_commute: true },
      { key: "b", rank: 2, score: 70, fits_budget: true, within_commute: false },
      { key: "c", rank: 3, score: 60, fits_budget: false, within_commute: true },
    ];
    assert.equal(liveSummary({ scores, total_regions: 143, excluded: [] }, true), "3 areas ranked · 1 fit your budget and trip");
    assert.equal(liveSummary({ scores, total_regions: 143, excluded: ["x"] }, true), "3 areas ranked · 1 fit your budget and trip · 1 removed");
  });

  test("compare marks the best value per row, and nothing when all are equal", () => {
    const rows = compareRows([region("A", 82, 650, 19, 0.7), region("B", 75, 720, 15, 0.7)], [w("green", 3)], "TU Berlin");
    const byLabel = Object.fromEntries(rows.map((r) => [r.label, r]));
    assert.deepEqual(byLabel["Match"].best, [0]);
    assert.deepEqual(byLabel["Typical warm rent"].best, [0]);
    assert.deepEqual(byLabel["Trip to TU Berlin"].best, [1]);
    assert.deepEqual(byLabel["green"].best, []); // a tie: no "best"
    assert.deepEqual(byLabel["green"].values, ["70/100", "70/100"]);
  });

  test("trip detail", () => {
    assert.equal(tripDetail(region("A", 1, 1, 19, 1)), "direct");
    assert.equal(tripDetail(region("A", 1, 1, null, 1)), null);
  });
});
