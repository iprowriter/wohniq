/**
 * AI explanations after the results (ADR-0022). /search answers in seconds with the
 * rule-based explanation; the page then sends each result's score breakdown to
 * /search/explanations and swaps in the model's wording where it came back. The model
 * writes only from these numbers, and anything it doesn't deliver keeps the rules text.
 */

import type { ExplainResponse, SearchResponse } from "./types.ts";

export const EXPLAIN_MAX = 20; // the endpoint's limit per request

export function explainRequest(data: SearchResponse) {
  return {
    criteria: data.criteria,
    items: data.results.slice(0, EXPLAIN_MAX).map((r) => ({
      listing_id: r.listing.id,
      score: r.score,
      factors: r.factors,
    })),
  };
}

/** Whether there is anything left to ask for (none yet, or a cached page without them). */
export function needsExplanations(data: SearchResponse): boolean {
  return data.results.some((r) => r.explanation_source === undefined);
}

export function mergeExplanations(data: SearchResponse, res: ExplainResponse): SearchResponse {
  const byId = new Map(res.items.map((i) => [i.listing_id, i]));
  return {
    ...data,
    results: data.results.map((r) => {
      const got = byId.get(r.listing.id);
      if (!got) return { ...r, explanation_source: r.explanation_source ?? "rules" };
      return got.source === "ai"
        ? { ...r, explanation: got.explanation, explanation_source: "ai" }
        : { ...r, explanation_source: "rules" };
    }),
  };
}
