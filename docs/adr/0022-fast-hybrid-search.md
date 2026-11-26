# ADR-0022 — Fast hybrid search: results first, AI wording after

**Status:** Accepted · **Date:** 2026-11-26 · Amends ADR-0001 (pipeline), ADR-0004 (LLM layer)

## Context

A live search took 2–3 minutes; offline demo mode took seconds. Timing one live search step
by step (page of 6; the site asks for 20) showed no single slow step, but about 20 slow
calls made one after another:

| Step | Calls | Time |
|---|---|---|
| Gemini parses the query | 1 | 5–10 s |
| Gemini explains each result | 1 per result | 45–55 s for 6 |
| Overpass neighbourhood counts | 1 per result | 12–13 s for 6 |
| BVG/VBB trip time (with a workplace) | 1 per result | up to 54 s for 6 |
| Retrieval and ranking | — | about 1 s |

Two more problems showed up while timing: 20 explanation calls per search would use the
free Gemini daily quota in about a dozen searches; and a Gemini service error (a retired
model id answered 404 for a new key) failed the whole search, because only *invalid
output* fell back to the deterministic path, not a failed call.

Once the calls ran in parallel, a further limit appeared: Supabase's **session pooler allows
15 clients in total**. The deployed backend keeps up to 15 idle connections between its two
pools (main and Berlin data), so lookups and local runs were refused (`EMAXCONNSESSION`)
and queued for minutes.

## Decision

The deterministic path, which already existed as the fallback, now answers first; the model
improves the wording when it can.

1. **Results first.** `/search` returns the rule-based explanation, written from the same
   score breakdown (`template_fallback`). The page then sends the breakdowns to
   `POST /search/explanations` and swaps in the model's wording as it arrives; where the
   request fails or an item is rejected, the rule-based text stays.
2. **Batched explanations** (`explain.batch.v1`): one Gemini call for up to 10 flats, the
   batches in parallel. So a page of 20 costs 2 calls instead of 20. Each item is validated
   as an `Explanation` on its own (golden rule 2); a missing, repeated, unknown or invalid
   item gets the template. The model's explanations are cached in memory by their exact
   input, so repeating a search costs no call.
3. **Time limits with a deterministic fallback.** Parsing is limited to
   `SEARCH_PARSE_TIMEOUT_S` (4 s), after which the keyword parser answers. Explanations
   have `SEARCH_EXPLAIN_TIMEOUT_S` (25 s) per batch.
4. **Any Gemini failure falls back.** Service errors (quota, retired model, network) are
   handled like invalid output. The model id is a setting (`GEMINI_CHAT_MODEL`, default
   `gemini-2.5-flash`), and thinking is off (`GEMINI_THINKING_BUDGET=0`) for these short
   structured tasks; a model that rejects the setting gets the call without it.
5. **Parallel page enrichment with a time limit** (`enrich/page.py`). Both caches are read
   for the whole page in two queries. The misses are looked up in parallel (2 at a time for
   Overpass, 6 for BVG/VBB), the same location never twice at once, the workplace resolved
   once. Whatever hasn't answered within `SEARCH_ENRICH_TIMEOUT_S` (2.5 s) gets the offline
   answer: the trip estimate (labelled as an estimate, ADR-0008/0009) and the bundled
   neighbourhood data. Late answers still fill the cache for the next search.
6. **No connection held while waiting.** A lookup holds no database connection during the
   outside call; it stores a live answer afterwards in a short session, one write at a time.
   Both engines turn off server-side prepared statements, so the **transaction pooler**
   (port 6543) works. It shares a few database connections among up to 200 clients.
   Production's `DATABASE_URL` should use it.

Ranking is unchanged and deterministic (golden rule 1); the model still writes only from
the breakdown (golden rule 3). The explanation request carries the breakdown and criteria
in its body; neither appears in a URL or in logs (ADR-0012).

## Consequences

- Measured locally against the live database, with the transaction pooler: results for 20
  flats in 5–9 s, the model's wording 5–18 s later. That was measured with
  `gemini-3.8-flash` (the local key can't use 2.5); production's `gemini-2.5-flash` with
  thinking off is expected to be faster, which also makes the 4 s parse limit rarely bite.
- When the trip or neighbourhood services are slow, more results show estimates on a first
  search; the next search finds the cached answers.
- The explanation endpoint trusts the breakdown it is sent. That only affects the
  sender's own page, since the model writes from the numbers it gets, and the input is
  bounded (20 items, 16 factors, short strings).
- `POST /compare` still explains with one call per flat (the compare page doesn't use it).
