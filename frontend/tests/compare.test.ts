// Compare list + compare page rows (T9.7) — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { cleanIds, compareHref, idFromLink, idsFromQuery, readCompare, toggleIn, writeCompare, MAX_COMPARE, COMPARE_STORAGE_KEY } from "../lib/compare/list.ts";
import { bestOf, compareGroups, type CompareFlat } from "../lib/compare/rows.ts";

class Mem {
  data = new Map<string, string>();
  get length() { return this.data.size; }
  clear() { this.data.clear(); }
  key(i: number) { return [...this.data.keys()][i] ?? null; }
  getItem(k: string) { return this.data.get(k) ?? null; }
  setItem(k: string, v: string) { this.data.set(k, v); }
  removeItem(k: string) { this.data.delete(k); }
}
const U = (n: number) => `00000000-0000-0000-0000-${String(n).padStart(12, "0")}`;

describe("compare list", () => {
  test("toggle adds and removes; a full list refuses a fifth flat", () => {
    let ids: string[] = [];
    for (let i = 1; i <= MAX_COMPARE; i++) ids = toggleIn(ids, U(i)).ids;
    const full = toggleIn(ids, U(9));
    assert.equal(full.ok, false);
    assert.equal(full.ids.length, 4);
    assert.deepEqual(toggleIn(ids, U(2)).ids, [U(1), U(3), U(4)]);
  });

  test("storage round trip; broken data reads as empty; junk ids dropped", () => {
    const s = new Mem() as unknown as Storage;
    writeCompare([U(1), U(1), "<x>", U(2)], s);
    assert.deepEqual(readCompare(s), [U(1), U(2)]);
    s.setItem(COMPARE_STORAGE_KEY, "nope");
    assert.deepEqual(readCompare(s), []);
    assert.deepEqual(cleanIds([1, "a b", "ok-1"]), ["ok-1"]);
  });

  test("ids in the address: at most four, clean", () => {
    assert.deepEqual(idsFromQuery(`${U(1)},${U(2)},,bad id,${U(1)}`), [U(1), U(2)]);
    assert.deepEqual(idsFromQuery(null), []);
    assert.equal(compareHref([U(1), U(2)]), `/compare?ids=${U(1)},${U(2)}`);
  });

  test("a pasted listing link or id gives the listing id", () => {
    assert.equal(idFromLink(`https://wohniq.app/listings/${U(7)}?from=x`), U(7));
    assert.equal(idFromLink(`  ${U(7).toUpperCase()} `), U(7));
    assert.equal(idFromLink("https://example.com/listing/123"), null);
  });
});

function flat(over: { warm: number; cold: number; size: number; risk?: number; band?: "low" | "high"; walk?: number; schools?: number; overMonth?: number | null; verdict?: string }): CompareFlat {
  return {
    detail: {
      listing: { id: "x", title: "t", address: "", kiez: "K", district: "D", rooms: 2, size_m2: over.size, kaltmiete_eur: over.cold, nebenkosten_eur: 0, warmmiete_eur: over.warm, deposit_eur: null, furnished: false, available_from: null, photos: [], description: "", lat: 0, lng: 0, anmeldung_possible: true },
      risk: over.risk == null ? null : { band: over.band ?? "low", score: over.risk, signals: over.band === "high" ? [{ name: "photo_reuse", source: "", evidence: "", severity: 1 }] : [] },
      rent: { verdict: (over.verdict ?? "within_limit") as never, verdict_text: "v", explanation: "", estimate: true, covered: true, over_per_month: over.overMonth ?? null, low: 10, high: 14, limit: 14.5 },
      location: { street: "", postcode: "", district: "D", location_class: "medium", east: false, rail_stop: "U X", rail_modes: [], rail_walk_minutes: over.walk ?? 5 },
    } as never,
    around: { lat: 0, lng: 0, measures: [{ key: "schools", label: "", source: "", headline: `${over.schools ?? 0} schools`, position: 0, comparison: "", detail: "", value: over.schools ?? 0 }, { key: "accidents", label: "", source: "", headline: "3 within 300 m", position: 0, comparison: "", detail: "", value: 3 }] },
  };
}

describe("compare rows", () => {
  test("bestOf: lower or higher wins; ties and single values mark nothing", () => {
    assert.deepEqual(bestOf([3, 1, 2], false), [1]);
    assert.deepEqual(bestOf([3, 1, 3], true), [0, 2]);
    assert.deepEqual(bestOf([2, 2], true), []);
    assert.deepEqual(bestOf([5, null], true), []);
  });

  test("price, risk, walk and schools mark the best column; accidents never do", () => {
    const groups = compareGroups([
      flat({ warm: 1200, cold: 900, size: 60, risk: 10, walk: 3, schools: 8 }),
      flat({ warm: 1000, cold: 800, size: 50, risk: 70, band: "high", walk: 9, schools: 2, overMonth: 120, verdict: "above_limit" }),
    ]);
    const r = Object.fromEntries(groups.flatMap((g) => g.rows).map((x) => [x.label, x]));
    assert.deepEqual(r["Warm rent"].best, [1]);
    assert.deepEqual(r["Size"].best, [0]);
    assert.deepEqual(r["Level"].best, [0]);
    assert.equal(r["Level"].values[1], "High (70/100)");
    assert.equal(r["Signals"].values[1], "photos used on another listing");
    assert.equal(r["Signals"].values[0], "No warning signs");
    assert.deepEqual(r["Verdict"].best, [0]); // 0 over vs €120 over
    assert.deepEqual(r["Nearest S/U-Bahn"].best, [0]);
    assert.deepEqual(r["Schools within 1 km"].best, [0]);
    assert.deepEqual(r["Road accidents"].best, []);
    assert.equal(r["Cold per m²"].values[0], "€15.00/m²");
    assert.equal(r["Trip to X"], undefined);
  });

  test("a trip row appears only when a place is chosen", () => {
    const a = { ...flat({ warm: 1, cold: 1, size: 1 }), trip: { minutes: 20, label: "20 min" } };
    const b = { ...flat({ warm: 1, cold: 1, size: 1 }), trip: { minutes: 31, label: "31 min, 1 change" } };
    const trip = compareGroups([a, b], "TU Berlin").flatMap((g) => g.rows).find((x) => x.label === "Trip to TU Berlin")!;
    assert.deepEqual(trip.values, ["20 min", "31 min, 1 change"]);
    assert.deepEqual(trip.best, [0]);
  });
});
