// AI explanations after the results (ADR-0022) — `npm test`.

import { describe, test } from "node:test";
import assert from "node:assert/strict";
import { EXPLAIN_MAX, explainRequest, mergeExplanations, needsExplanations } from "../lib/explanations.ts";
import type { SearchResponse, SearchResultItem } from "../lib/types.ts";

const item = (id: string, summary = `rules ${id}`): SearchResultItem =>
  ({
    listing: { id } as SearchResultItem["listing"],
    score: 0.7,
    factors: [{ name: "budget", score: 0.9, weight: 2, detail: "€900 warm", highlight: "" }],
    explanation: { summary, reasons: [], caveats: [] },
  }) as SearchResultItem;

const page = (n: number): SearchResponse => ({
  criteria: { transport_priority: false, quiet_priority: true, desired_amenities: [] },
  results: Array.from({ length: n }, (_, i) => item(`id${i}`)),
});

describe("explanations", () => {
  test("the request carries criteria and breakdowns only, at most the endpoint limit", () => {
    const body = explainRequest(page(25));
    assert.equal(body.items.length, EXPLAIN_MAX);
    assert.deepEqual(Object.keys(body.items[0]).sort(), ["factors", "listing_id", "score"]);
    assert.equal(body.criteria.quiet_priority, true);
  });

  test("model wording replaces the rules text; rules and missing items keep it", () => {
    const data = page(3);
    const merged = mergeExplanations(data, {
      items: [
        { listing_id: "id0", source: "ai", explanation: { summary: "AI says", reasons: ["r"], caveats: [] } },
        { listing_id: "id1", source: "rules", explanation: { summary: "ignored", reasons: [], caveats: [] } },
      ],
    });
    assert.equal(merged.results[0].explanation.summary, "AI says");
    assert.equal(merged.results[0].explanation_source, "ai");
    assert.equal(merged.results[1].explanation.summary, "rules id1");
    assert.equal(merged.results[2].explanation.summary, "rules id2");
    assert.ok(merged.results.every((r) => r.explanation_source));
    assert.equal(data.results[0].explanation.summary, "rules id0"); // input untouched
  });

  test("asks only while some result hasn't been through it", () => {
    const data = page(2);
    assert.equal(needsExplanations(data), true);
    assert.equal(needsExplanations(mergeExplanations(data, { items: [] })), false);
  });
});
