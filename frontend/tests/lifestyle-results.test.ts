// Lifestyle Match results-page logic — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { Catalog, WeightOut } from "../lib/lifestyle/types.ts";
import { clearState, defaultAnswers, type StorageLike } from "../lib/lifestyle/logic.ts";
import {
  EXCLUDED_COLOR,
  RESULTS_KEY,
  SCORE_BANDS,
  activeCount,
  addExcluded,
  answersFingerprint,
  commuteLabel,
  loadAdjustments,
  pendingChanges,
  removeExcluded,
  sameWeights,
  saveAdjustments,
  scoreColor,
  setWeight,
  sourceChip,
  sourceIndex,
  weightMap,
  yearSpan,
  weightOverrides,
} from "../lib/lifestyle/results.ts";

const catalog: Catalog = JSON.parse(
  readFileSync(new URL("./fixtures/lifestyle-catalog.json", import.meta.url), "utf-8"),
);

class MemoryStorage implements StorageLike {
  data = new Map<string, string>();
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
  removeItem(k: string) {
    this.data.delete(k);
  }
}

const w = (attribute: string, value: number): WeightOut => ({
  attribute,
  label: attribute,
  value,
  reasons: [],
  overridden: false,
});

describe("weights", () => {
  const base = weightMap([w("commute", 5), w("cafes", 3), w("safety", 0)]);

  test("only changed weights are sent as overrides", () => {
    assert.deepEqual(weightOverrides(base, { ...base }), {});
    assert.deepEqual(weightOverrides(base, { ...base, cafes: 5, safety: 2 }), { cafes: 5, safety: 2 });
    // Moving a slider back to the answer's value is not an override.
    assert.deepEqual(weightOverrides(base, { ...base, cafes: 3 }), {});
    // Attributes missing from the base count as 0.
    assert.deepEqual(weightOverrides(base, { ...base, water: 0 }), {});
  });

  test("pending changes count sliders that differ from the applied result", () => {
    assert.equal(pendingChanges(base, base), 0);
    assert.equal(pendingChanges(base, { ...base, cafes: 4, safety: 1 }), 2);
    assert.ok(sameWeights(base, { ...base, water: 0 }));
    assert.ok(!sameWeights(base, { ...base, cafes: 1 }));
  });

  test("slider values are clamped to 0–5 integers", () => {
    assert.equal(setWeight(base, "cafes", 9).cafes, 5);
    assert.equal(setWeight(base, "cafes", -3).cafes, 0);
    assert.equal(setWeight(base, "cafes", 2.6).cafes, 3);
    assert.equal(activeCount({ a: 0, b: 2, c: 5 }), 2);
  });
});

describe("removed areas", () => {
  test("remove and undo", () => {
    const once = addExcluded([], "043006");
    assert.deepEqual(addExcluded(once, "043006"), ["043006"]); // no duplicates
    assert.deepEqual(removeExcluded(addExcluded(once, "071001"), "043006"), ["071001"]);
  });
});

describe("map colours", () => {
  test("bands are ordered and every score gets a colour", () => {
    const mins = SCORE_BANDS.map((b) => b.min);
    assert.deepEqual(mins, [...mins].sort((a, b) => b - a));
    assert.equal(scoreColor(95), SCORE_BANDS[0].color);
    assert.equal(scoreColor(80), SCORE_BANDS[0].color);
    assert.equal(scoreColor(79), SCORE_BANDS[1].color);
    assert.equal(scoreColor(0), SCORE_BANDS[SCORE_BANDS.length - 1].color);
    assert.equal(scoreColor(null), EXCLUDED_COLOR);
  });
});

describe("sources and labels", () => {
  const index = sourceIndex(catalog.sources);

  test("every source id in the catalog resolves, and chips are short", () => {
    assert.equal(Object.keys(index).length, catalog.sources.length);
    assert.equal(sourceChip(index.pks_kriminalitaetsatlas), "Polizei Berlin · 2023–2025");
    assert.equal(sourceChip(index.openstreetmap_geofabrik), "OpenStreetMap · 2026");
    assert.equal(sourceChip(index.vbb_gtfs), "VBB timetable · 2026");
    assert.equal(sourceChip(index.umweltgerechtigkeitsatlas_2023_2024), "Umweltatlas · 2020–2023");
    for (const s of catalog.sources) assert.ok(sourceChip(s).length <= 40, sourceChip(s));
    assert.equal(sourceChip(undefined), "Source");
  });

  test("year spans", () => {
    assert.equal(yearSpan("2025"), "2025");
    assert.equal(yearSpan("2023–2025"), "2023–2025");
    assert.equal(yearSpan("noise 2022 · air 2023 · heat 2022 · green space 2020"), "2020–2023");
  });

  test("commute labels", () => {
    assert.equal(commuteLabel(15, 0), "≈ 15 min, direct");
    assert.equal(commuteLabel(24, 1), "≈ 24 min, 1 change");
    assert.equal(commuteLabel(31, 2), "≈ 31 min, 2 changes");
    assert.equal(commuteLabel(20, null, true), "≈ 20 min");
  });
});

describe("adjustments in session storage", () => {
  const answers = { ...defaultAnswers(), evenings: "calm" };

  test("round trip for the same answers", () => {
    const s = new MemoryStorage();
    saveAdjustments(s, { overrides: { cafes: 5 }, excluded: ["043006"] }, answers);
    assert.deepEqual(loadAdjustments(s, answers), { overrides: { cafes: 5 }, excluded: ["043006"] });
  });

  test("changed answers drop slider overrides but keep removed areas", () => {
    const s = new MemoryStorage();
    saveAdjustments(s, { overrides: { cafes: 5 }, excluded: ["043006"] }, answers);
    const changed = { ...answers, evenings: "out_often" };
    assert.deepEqual(loadAdjustments(s, changed), { overrides: {}, excluded: ["043006"] });
    assert.notEqual(answersFingerprint(answers), answersFingerprint(changed));
  });

  test("invalid stored values are ignored", () => {
    const s = new MemoryStorage();
    s.setItem(
      RESULTS_KEY,
      JSON.stringify({
        v: 1,
        answers: answersFingerprint(answers),
        overrides: { cafes: 9, water: "x", quiet: 2.5, green: 3 },
        excluded: ["043006", "DROP TABLE", 12],
      }),
    );
    assert.deepEqual(loadAdjustments(s, answers), { overrides: { green: 3 }, excluded: ["043006"] });
    s.setItem(RESULTS_KEY, "{oops");
    assert.deepEqual(loadAdjustments(s, answers), { overrides: {}, excluded: [] });
  });

  test("'Clear my answers' also clears the adjustments", () => {
    const s = new MemoryStorage();
    saveAdjustments(s, { overrides: { cafes: 5 }, excluded: [] }, answers);
    clearState(s);
    assert.equal(s.getItem(RESULTS_KEY), null);
  });
});
