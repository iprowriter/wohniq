// Rent check texts and helpers — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkRent, rentByPeriod, type RentInput } from "../lib/rent/check.ts";
import { explainResult, VERDICT_TITLE } from "../lib/rent/explain.ts";
import { isFairRent, rentChip, riskChip, worthAsking } from "../lib/listing/chips.ts";
import type { RentOut, RiskOut } from "../lib/types.ts";

const fx = JSON.parse(readFileSync(new URL("./fixtures/rent-vectors.json", import.meta.url), "utf8"));
const run = (name: string) => {
  const v = fx.vectors.find((x: { name: string }) => x.name === name);
  return { r: checkRent(v.input as RentInput, fx.rows, fx.periods, fx.checklist), v };
};

describe("rent check texts", () => {
  test("above the limit names the amount a month", () => {
    const { r } = run("index only, above");
    assert.equal(VERDICT_TITLE[r.verdict], "Your rent is above the rent-brake limit");
    const text = explainResult(r, 61);
    assert.match(text, /You pay €14\.10\/m² cold/);
    assert.match(text, /allows up to €10\.41\/m² \(€635 cold\)/);
    assert.match(text, /about €225 a month over the limit/);
  });

  test("brochure example: groups counted and the comparable rent named", () => {
    const { r } = run("brochure example 10.4 B");
    const text = explainResult(r, 60);
    assert.match(text, /3 feature groups raising the value and 2 lowering it, the comparable rent is €7\.75\/m²/);
    assert.match(text, /under the limit/);
  });

  test("new builds and flats after 2024", () => {
    assert.match(explainResult(run("new build").r, 80), /no legal maximum/);
    assert.match(explainResult(run("after 2024").r, 80), /up to 2024/);
  });

  test("mean by building age for the chart", () => {
    const bars = rentByPeriod(fx.rows, "medium", true, 38, fx.periods);
    assert.deepEqual(bars.map((b) => b.period), ["1919-1949", "1973-1990-east"]);
  });
});

describe("listing chips", () => {
  const rent = { verdict: "above_limit", asked: 17.45, low: 6.64, high: 11.0, limit: 8.88,
    over_per_month: 283, verdict_text: "", explanation: "", estimate: true, covered: true } as const;
  test("rent chips carry words and numbers", () => {
    assert.equal(rentChip(rent)?.text, "Above limit · €17.45/m² vs limit €8.88");
    assert.equal(rentChip({ ...rent, verdict: "within_limit", asked: 6.91, low: 5.9, high: 9.55 })?.text,
      "Fair rent · €6.91/m² cold (index €5.90–9.55)");
    assert.equal(rentChip({ ...rent, verdict: "new_build" })?.tone, "neutral");
    assert.ok(isFairRent({ ...rent, verdict: "within_limit" }) && !isFairRent(rent));
    // Map points carry only the verdict: a short chip, never a crash.
    assert.equal(rentChip({ verdict: "within_limit" } as unknown as RentOut)?.text, "Fair rent");
    assert.equal(rentChip({ verdict: "above_limit" } as unknown as RentOut)?.tone, "warn");
  });
  test("risk chips never use red wording", () => {
    assert.equal(riskChip({ band: "high", score: 90, signals: [] })?.text, "High risk: read why");
    assert.equal(riskChip({ band: "low", score: 0, signals: [] })?.tone, "ok");
  });
  test("worth asking prefers a risk signal, then the rent", () => {
    assert.match(worthAsking(rent, null)!, /about €283 a month over the rent-brake limit/);
    const risk: RiskOut = {
      band: "caution",
      score: 54,
      signals: [{ name: "x", source: "rule", evidence: '"Pay first."', severity: 1 }],
    };
    assert.equal(worthAsking(rent, risk), "Worth asking: Pay first.");
  });
});
