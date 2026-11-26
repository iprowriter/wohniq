// Search results view logic — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { readParams, resultsHeading, sortResults, toQuery, visibleResults } from "../lib/results.ts";
import type { SearchResultItem } from "../lib/types.ts";

function item(id: string, score: number, warm: number, size: number, asked?: number, limit?: number): SearchResultItem {
  return {
    score,
    factors: [],
    explanation: { summary: "", reasons: [], caveats: [] },
    listing: {
      id, title: id, address: "", kiez: "Mitte", rooms: 2, size_m2: size, kaltmiete_eur: 0,
      nebenkosten_eur: 0, warmmiete_eur: warm, furnished: false, photos: [],
      rent: asked == null ? null : {
        verdict: asked <= (limit ?? 0) ? "within_limit" : "above_limit", verdict_text: "",
        explanation: "", estimate: true, covered: true, asked, limit,
      },
    },
  };
}

const A = item("a", 0.9, 1200, 50, 12, 10); // above
const B = item("b", 0.8, 900, 70, 8, 9); // fair
const C = item("c", 0.7, 1000, 60); // new build / unknown

describe("results", () => {
  test("fit keeps the backend order; other sorts re-order by the picked field", () => {
    assert.deepEqual(sortResults([A, B, C], "fit").map((i) => i.listing.id), ["a", "b", "c"]);
    assert.deepEqual(sortResults([A, B, C], "price").map((i) => i.listing.id), ["b", "c", "a"]);
    assert.deepEqual(sortResults([A, B, C], "rent").map((i) => i.listing.id), ["b", "a", "c"]);
    assert.deepEqual(sortResults([A, B, C], "size").map((i) => i.listing.id), ["b", "c", "a"]);
  });

  test("only fair rents keeps flats within the rent-brake limit", () => {
    assert.deepEqual(visibleResults([A, B, C], true, "fit").map((i) => i.listing.id), ["b"]);
  });

  test("headings", () => {
    assert.equal(resultsHeading(8, ["Mitte"]), "8 flats in Mitte");
    assert.equal(resultsHeading(1, []), "1 flat for your search");
    assert.equal(resultsHeading(0, ["Mitte", "Spandau"]), "0 flats in Mitte, Spandau");
  });

  test("searches round-trip through the URL; flat details never go in it", () => {
    const s = { q: "quiet flat in Mitte", fair: true, sort: "price" as const, budget: 1400 };
    assert.deepEqual(readParams(new URLSearchParams(toQuery(s))), s);
    assert.equal(readParams(new URLSearchParams("")), null);
    assert.equal(readParams(new URLSearchParams("q=x&sort=bogus"))?.sort, "fit");
  });
});
