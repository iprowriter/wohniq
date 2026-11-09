# ADR-0012 — Privacy by design: lifestyle answers are never stored or logged

**Status:** Accepted (Step 3 of Lifestyle Match) · **Date:** 2026-11-09

## Context

Lifestyle Match asks about how people live: budget, where they study or work, how they spend evenings, whether crime worries them. Individually harmless, together these describe a person. The product requirement: *a user's answers are not stored in our database or logged*. The existing search path also leaked user input. `/search` logged the raw query and parsed values (budget, work location). A failed commute lookup logged the typed work location. LLM validation failures logged model output, which can echo the query.

## Decision

**1. Collect less.**
- Answers are fixed choices and bounded numbers only; `Answers` rejects unknown fields (`extra="forbid"`). There are no free-text fields.
- Destinations are ids from a fixed list of 13 campuses and hubs, so no address is typed, geocoded or sent to a transit API.
- No question asks about age, gender, origin, religion, health or income. Tests check the question copy.
- The listing hand-off receives only what it needs: region, budget, minimum rooms.

**2. Keep nothing.**
- `/lifestyle/profile` and `/lifestyle/match` are pure functions of the request and the shipped, read-only region data. They have no repository dependency at all; a test fails if one is requested.
- `/lifestyle/listings` reads listings and writes nothing.
- No cookies, no session, no server-side cache. POST responses are `Cache-Control: no-store`.

**3. Log nothing identifying.**
- Lifestyle endpoints log counts and latency only.
- Answers travel in POST bodies, never in URLs, so access logs (which record paths) can't capture them. A test checks that every lifestyle route taking user input is POST-only, and every GET route takes no query parameters.
- `/search` now logs the number of results and the *names* of the fields the parser understood, not the query or the values.
- Commute-lookup failures log the listing origin and the error type, not the destination.
- LLM validation failures log the number and location of errors (`max_warm_rent`), not the invalid values.

**4. No third parties.** Lifestyle Match makes no LLM, geocoding or transit-API calls at request time. All data is precomputed (ADR-0010, ADR-0011).

**5. Client side** (Steps 4–5). Answers live in React state and `sessionStorage` (cleared when the tab closes), with a visible "Clear my answers" action. They are never written to `localStorage`, cookies or the URL. There is no analytics.

## Verification

`tests/test_lifestyle_privacy.py` sends distinctive values (budget €4,321, 187 m², a destination, an excluded region) through every endpoint with all loggers captured at DEBUG. It asserts none of them appears in any log message, argument or exception text. The same is done for `/search` (query text, parsed budget and work location), commute failures and LLM validation failures. The test was checked against a deliberately injected `logger.debug(answers)` and fails as intended. `make eval-lifestyle` adds checks that answers reject unknown fields, that questions are fixed choices, and that destinations are a fixed list.

## Alternatives considered

- **Store anonymised answers for analytics:** rejected. Not needed for the feature, and "anonymised" lifestyle profiles are easy to re-identify.
- **Hash sensitive log values:** rejected for answers. Low-entropy values (a budget, a campus) are trivially reversible.
- **Send answers to an LLM for the persona text:** rejected (ADR-0011). Deterministic templates need no third party.

## Consequences

- **+** The Definition of Done's privacy clause is enforced by tests, not just by convention.
- **+** Debugging relies on counts, latency, and reproducing requests locally (results are deterministic, so a bug report with the answers reproduces exactly).
- **−** We can't learn which answers are popular. That would need explicit, opt-in, aggregate counting: a separate decision.
- **Open item (not Lifestyle Match):** the `/search` commute cache (`commute_cache`, ADR-0005/T4.1) still stores the normalised work location typed into free-text search as part of its cache key. Options: drop caching for free-text destinations, or expire entries quickly.
