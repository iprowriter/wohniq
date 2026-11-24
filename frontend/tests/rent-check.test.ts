// Rent check in the browser — `npm test`. Must reproduce the Python reference exactly
// (vectors from backend `python -m data.berlin.export_rent_vectors`, ADR-0017).

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ageOptions, checkRent, periodFor, type RentInput } from "../lib/rent/check.ts";

const fixture = JSON.parse(readFileSync(new URL("./fixtures/rent-vectors.json", import.meta.url), "utf8"));

describe("rent check matches the Python reference", () => {
  for (const v of fixture.vectors) {
    test(v.name, () => {
      const r = checkRent(v.input as RentInput, fixture.rows, fixture.periods, fixture.checklist);
      const e = v.expected;
      assert.equal(r.row?.row ?? null, e.row);
      assert.deepEqual(r.groups.map((g) => g.effect), e.groups);
      for (const key of ["covered", "period", "low", "mean", "high", "net_groups", "used_checklist",
        "comparable", "limit", "exempt", "asked", "verdict", "over_per_m2", "over_per_month",
        "ignored_features"] as const) {
        assert.deepEqual(r[key], e[key], key);
      }
    });
  }
});

describe("building-age choices", () => {
  test("East shows 1973–1990 as one band, West splits it", () => {
    assert.ok(ageOptions(true).some((o) => o.label === "1973–1990"));
    assert.ok(ageOptions(false).some((o) => o.label === "1973–1985"));
  });

  test("every choice maps to a Mietspiegel period (or none after 2024)", () => {
    for (const east of [true, false]) {
      for (const o of ageOptions(east)) {
        const p = periodFor(o.year, east, fixture.periods);
        if (o.id === "2025") assert.equal(p, null);
        else assert.ok(p, o.label);
      }
    }
  });
});
