# ADR-0020 — Saved searches in the browser, with download and import

**Status:** Accepted · **Date:** 2026-11-26 · Extends the saved flats of T9.4

## Context

Users could save flats (listing ids in `localStorage`, `/saved`) but not a search. WohnIQ has
no accounts and adds no paid service (ADR-0003), and Lifestyle answers deliberately stay
temporary (ADR-0012). The owner asked for saved searches without an account, "new since last
time" badges, and a way to move saved items to another browser.

## Decision

1. **Only on request, only in this browser.** "Save search" above the results stores the
   query, "Only fair rents", the sort, the budget, a name (the query by default), the save
   date and the result ids of the last run, under `wohniq_saved_searches_v1` (versioned,
   max 30 searches, max 200 ids each). Broken or foreign data reads as empty. Nothing is sent
   to the server except the query when the search runs, as before.
2. **One search per question.** Two searches are the same when the normalised query and
   budget match; sort and the fair-rent filter only reorder, so saving again updates the
   entry instead of adding one.
3. **New since last time.** When a saved search runs again, results whose ids were not in the
   previous run get a "New" badge and a line says how many and since when; then the record is
   updated to this run. The demo catalogue never changes, so normally "No new flats".
4. **Where they appear.** A "Your saved searches" row under the home search box (one click
   runs it), `/saved` with Flats and Searches tabs (run, rename, delete, delete all), and the
   header count covers both.
5. **Download / import.** One JSON file (`app: "WohnIQ"`, `kind: "wohniq-saved-items"`,
   `v: 1`) with flat ids and searches. Import only adds what is missing, never overwrites,
   drops malformed entries and refuses other files and files over 500 kB.

## Consequences

- No account, no server state, €0; clearing site data removes saved items (said on the page).
- Listing ids and search text are not personal data in the sense of the Lifestyle answers;
  Lifestyle answers are still never saved.
- Tests: `tests/saved-searches.test.ts` (storage, limits, broken data, new since, import),
  `e2e/saved-searches.spec.ts` (save → home row → run, rename/delete, New badges, download →
  import into an empty browser, foreign file refused).
