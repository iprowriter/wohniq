// Lifestyle Match questionnaire logic — run with `npm test` (Node's built-in runner,
// TypeScript via type stripping; no extra dependencies).

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { Answers, Catalog } from "../lib/lifestyle/types.ts";
import {
  LIMITS,
  MULTI_QUESTIONS,
  SINGLE_QUESTIONS,
  STORAGE_KEY,
  SUMMARY,
  WELCOME,
  budgetReferences,
  chooseSingle,
  clampNumber,
  clearState,
  defaultAnswers,
  fromPreset,
  groupDestinations,
  hasAnyPreference,
  loadState,
  nextStep,
  normalizeAnswers,
  optionEffect,
  pageIssues,
  prevStep,
  progress,
  saveState,
  setDestination,
  stepsFor,
  toRequestAnswers,
  toggleMulti,
  typicalBerlinWarmRent,
  type StorageLike,
} from "../lib/lifestyle/logic.ts";

// The real /lifestyle/catalog response, exported by the backend (`make lifestyle-fixture`).
const catalog: Catalog = JSON.parse(
  readFileSync(new URL("./fixtures/lifestyle-catalog.json", import.meta.url), "utf-8"),
);
const question = (id: string) => {
  const q = catalog.questions.find((x) => x.id === id);
  assert.ok(q, `question ${id} missing from catalog`);
  return q;
};

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

describe("contract with the backend catalog", () => {
  test("question ids match the answer fields the frontend knows", () => {
    const ids = catalog.questions.map((q) => q.id).sort();
    assert.deepEqual(ids, [...SINGLE_QUESTIONS, ...MULTI_QUESTIONS].sort());
    for (const q of catalog.questions) {
      assert.equal(q.multi, (MULTI_QUESTIONS as string[]).includes(q.id), q.id);
    }
  });

  test("every preset survives normalisation unchanged", () => {
    assert.equal(catalog.presets.length, 5);
    for (const p of catalog.presets) {
      const a = fromPreset(p);
      assert.deepEqual(toRequestAnswers(a), toRequestAnswers(p.answers as Answers), p.id);
    }
  });

  test("student preset matches the agreed defaults", () => {
    const student = catalog.presets.find((p) => p.id === "student")!;
    assert.equal(student.answers.size_m2, 30);
    assert.equal(student.answers.budget_eur, 700);
    assert.equal(student.answers.destination, "tu_berlin");
  });

  test("pages and steps", () => {
    const steps = stepsFor(catalog);
    assert.deepEqual(steps, [WELCOME, "move", "days", "free_time", "neighbourhood", SUMMARY]);
  });
});

describe("steps", () => {
  const steps = stepsFor(catalog);
  test("next/prev stay in bounds", () => {
    assert.equal(nextStep(steps, WELCOME), "move");
    assert.equal(nextStep(steps, SUMMARY), SUMMARY);
    assert.equal(prevStep(steps, "move"), WELCOME);
    assert.equal(prevStep(steps, WELCOME), WELCOME);
    assert.equal(prevStep(steps, "unknown-step"), WELCOME);
  });
  test("progress runs from 0 to 1", () => {
    assert.equal(progress(steps, WELCOME), 0);
    assert.equal(progress(steps, SUMMARY), 1);
    assert.ok(progress(steps, "days") > progress(steps, "move"));
  });
});

describe("answers", () => {
  test("defaults are within the backend's bounds", () => {
    const a = defaultAnswers();
    assert.ok(a.budget_eur >= LIMITS.budget.min && a.budget_eur <= LIMITS.budget.max);
    assert.ok(a.size_m2 >= LIMITS.size.min && a.size_m2 <= LIMITS.size.max);
    assert.deepEqual(pageIssues("move", a), []);
  });

  test("single choice toggles, multi choice respects the maximum", () => {
    let a = chooseSingle(defaultAnswers(), "evenings", "out_often");
    assert.equal(a.evenings, "out_often");
    a = chooseSingle(a, "evenings", "out_often");
    assert.equal(a.evenings, null);

    const max = question("weekends").max_choices;
    let b = toggleMulti(defaultAnswers(), "weekends", "nature", max);
    b = toggleMulti(b, "weekends", "culture", max);
    const full = toggleMulti(b, "weekends", "active", max);
    assert.deepEqual(full.weekends, ["nature", "culture"]); // third choice refused
    assert.deepEqual(toggleMulti(full, "weekends", "nature", max).weekends, ["culture"]);
  });

  test("choosing no destination clears the frequency", () => {
    const a = setDestination(defaultAnswers(), "tu_berlin");
    assert.equal(a.frequency, "daily");
    const b = setDestination({ ...a, frequency: "rarely" }, null);
    assert.equal(b.destination, null);
    assert.equal(b.frequency, null);
  });

  test("page validation flags out-of-range numbers", () => {
    assert.equal(pageIssues("move", { ...defaultAnswers(), budget_eur: 50 }).length, 1);
    assert.equal(pageIssues("move", { ...defaultAnswers(), size_m2: 900 }).length, 1);
    assert.equal(pageIssues("days", { ...defaultAnswers(), max_commute_min: 5 }).length, 1);
    assert.deepEqual(pageIssues("free_time", defaultAnswers()), []);
  });

  test("a preference is needed before matching", () => {
    assert.equal(hasAnyPreference(defaultAnswers(), catalog), false);
    assert.equal(hasAnyPreference({ ...defaultAnswers(), evenings: "out_often" }, catalog), true);
    // How often you commute only counts once there's a destination.
    assert.equal(hasAnyPreference({ ...defaultAnswers(), frequency: "daily" }, catalog), false);
    // "Just me" sets no weight.
    assert.equal(hasAnyPreference({ ...defaultAnswers(), household: "solo" }, catalog), false);
  });

  test("clampNumber", () => {
    assert.equal(clampNumber(5, 10, 20), 10);
    assert.equal(clampNumber(25, 10, 20), 20);
    assert.equal(clampNumber(2.26, 1, 8, 0.5), 2.5);
    assert.equal(clampNumber(Number.NaN, 1, 8), 1);
  });
});

describe("privacy", () => {
  test("request body contains the fixed answer fields only", () => {
    const dirty = { ...defaultAnswers(), name: "Alex", email: "a@example.org" } as Answers;
    const body = toRequestAnswers(dirty);
    assert.deepEqual(Object.keys(body).sort(), Object.keys(defaultAnswers()).sort());
    assert.ok(!("name" in body) && !("email" in body));
  });

  test("frequency is dropped without a destination; numbers are integers", () => {
    const body = toRequestAnswers({ ...defaultAnswers(), frequency: "daily", budget_eur: 700.4 });
    assert.equal(body.frequency, null);
    assert.equal(body.budget_eur, 700);
  });

  test("restored data is sanitised: unknown keys dropped, numbers clamped, arrays deduped", () => {
    const a = normalizeAnswers({
      budget_eur: 999999,
      size_m2: 30,
      weekends: ["nature", "nature", 3],
      evenings: 42,
      secret: "x",
    });
    assert.ok(a);
    assert.equal(a.budget_eur, LIMITS.budget.max);
    assert.deepEqual(a.weekends, ["nature"]);
    assert.equal(a.evenings, null);
    assert.ok(!("secret" in a));
    assert.equal(normalizeAnswers({ size_m2: 30 }), null);
    assert.equal(normalizeAnswers("nope"), null);
  });

  test("session storage: round trip, version check, corruption, clear", () => {
    const storage = new MemoryStorage();
    const answers = { ...defaultAnswers(), evenings: "calm" };
    saveState(storage, { answers, step: "days", presetId: "calm_green" });
    assert.deepEqual(loadState(storage), { answers, step: "days", presetId: "calm_green" });

    storage.setItem(STORAGE_KEY, JSON.stringify({ v: 999, answers }));
    assert.equal(loadState(storage), null);
    storage.setItem(STORAGE_KEY, "{not json");
    assert.equal(loadState(storage), null);

    clearState(storage);
    assert.equal(storage.getItem(STORAGE_KEY), null);
  });

  test("storage failures never break the questionnaire", () => {
    const broken: StorageLike = {
      getItem() {
        throw new Error("denied");
      },
      setItem() {
        throw new Error("quota");
      },
      removeItem() {
        throw new Error("denied");
      },
    };
    saveState(broken, { answers: defaultAnswers(), step: WELCOME, presetId: null });
    assert.equal(loadState(broken), null);
    clearState(broken);
  });
});

describe("presentation", () => {
  test("option tooltips say which weights an answer sets", () => {
    const labels = Object.fromEntries(catalog.attributes.map((a) => [a.id, a.label]));
    const outOften = question("evenings").options.find((o) => o.id === "out_often")!;
    assert.equal(optionEffect(outOften, labels), "Sets importance: Nightlife 5/5");
    const solo = question("household").options.find((o) => o.id === "solo")!;
    assert.equal(optionEffect(solo, labels), "Doesn't change any weights");
  });

  test("budget references come from cited city figures", () => {
    // (15.78 median + 1.93 + 1.50 running costs) × 30 m² = 576.3
    assert.equal(typicalBerlinWarmRent(catalog.city, 30), 576);
    const refs = budgetReferences(catalog.city, 30);
    assert.deepEqual(
      refs.map((r) => r.value),
      [380, 650, 576],
    );
    assert.equal(typicalBerlinWarmRent({}, 30), null);
  });

  test("destinations are grouped into campuses and hubs", () => {
    const g = groupDestinations(catalog.destinations);
    assert.equal(g.university.length + g.hub.length, catalog.destinations.length);
    assert.ok(g.university.some((d) => d.id === "tu_berlin"));
    assert.ok(g.hub.some((d) => d.id === "alexanderplatz"));
  });
});
