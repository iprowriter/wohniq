// Listing page logic — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { riskChecks } from "../lib/listing/riskChecks.ts";
import { backLabel, fitLabel, readLastSearch, saveLastSearch } from "../lib/listing/lastSearch.ts";
import type { RiskOut } from "../lib/types.ts";

class MemStorage {
  data = new Map<string, string>();
  getItem(k: string) { return this.data.get(k) ?? null; }
  setItem(k: string, v: string) { this.data.set(k, v); }
}

describe("risk checks", () => {
  test("low risk lists the checks that passed, from data only", () => {
    const low: RiskOut = { band: "low", score: 0, signals: [] };
    const c = riskChecks(low, { verdict: "above_limit" } as never, true);
    assert.equal(c.title, "Why the risk is low");
    assert.equal(c.passed.length, 4);
    assert.match(c.passed[0], /above the rent-brake limit: ask about that separately/);
    assert.match(c.checked, /Score 0\/100\.$/);
  });

  test("signals become questions to ask, and their checks drop out", () => {
    const high: RiskOut = {
      band: "high",
      score: 95,
      signals: [
        { name: "price_below_index", source: "rule", evidence: "€4.22/m² cold is 50% below…", severity: 1 },
        { name: "off_platform_payment", source: "rule", evidence: '"Pay via Western Union."', severity: 0.85 },
      ],
    };
    const c = riskChecks(high, null, false);
    assert.equal(c.title, "What to ask before you go further");
    assert.deepEqual(c.flagged, ["€4.22/m² cold is 50% below…", "“Pay via Western Union.”"]);
    assert.deepEqual(c.passed, ["The photos don't appear as a set on any other listing."]);
  });
});

describe("last search", () => {
  test("round-trips and builds the back link", () => {
    const store = new MemStorage() as unknown as Storage;
    assert.equal(readLastSearch(store), null);
    saveLastSearch({ url: "/?q=x", heading: "8 flats in Mitte", count: 8, areas: ["Mitte"], fit: { a: { score: 0.92, summary: "s" } } }, store);
    const s = readLastSearch(store);
    assert.equal(backLabel(s), "Back to 8 results in Mitte");
    assert.equal(backLabel(null), "Back to search");
    assert.equal(fitLabel(0.92), "Strong match");
  });
});
