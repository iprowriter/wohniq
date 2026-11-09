# ADR-0011 — Lifestyle Match: answers → weights → deterministic, explained ranking

**Status:** Accepted (Step 2 of Lifestyle Match) · **Date:** 2026-11-09

## Context

Lifestyle Match asks a short questionnaire and recommends Berlin regions (ADR-0010 profiles). The recommendation must be reproducible, explainable with the data behind it, adjustable by the user, and private. ADR-0001 already settles *who* ranks: code, not the LLM. This ADR settles *how*.

## Decision

1. **Bounded answers only.** `Answers` (lifestyle/questionnaire.py) accepts choices from fixed lists and bounded numbers; unknown fields are rejected (`extra="forbid"`). There is no free text, and destinations are ids from a fixed list of 13 campuses and hubs. Nothing a user submits can identify them, and nothing needs to be geocoded or sent to a third party. No question asks about age, gender, origin, religion, health or income (a test checks the copy).
2. **Answers → weights by "max level".** Each option sets importance levels 0–5 for some attributes, in one table. An attribute's weight is the highest level any chosen option gives it. This keeps weights on one scale, is independent of answer order, and every weight can cite the answer(s) that set it. Users can override any weight (`apply_overrides`). **Presets are pre-filled answers**, not a separate mechanism. A test checks that they reproduce the approved preset weights exactly.
3. **Weights × profiles → score.** For each region, `total = Σ w·s / Σ w` over weighted attributes with data, where `s ∈ [0, 1]`:
   - area attributes use the bundle's fixed normalisation (ADR-0010);
   - **affordability**: typical warm rent = (district median asking rent + average running costs €3.43/m²) × the user's flat size, scored with `limit_score` (full marks ≤ 70% of budget, half at 100%, zero from 130%);
   - **commute**: public-transport minutes from the region's resident-weighted centre to the chosen destination, **precomputed at build time** over the VBB weekday-peak network (ADR-0009), scored with the same shape (full ≤ 10 min, half at the user's maximum, zero at 1.5×).
   A weighted attribute that can't be scored (e.g. commute with no destination) is reported as *unscored*, never counted as zero.
4. **Ranking is lexicographic.** Regions where a typical flat fits the budget come first. Over-budget regions are still shown, ranked after them (product decision). Then, within each group, regions within the maximum commute come first. Then higher total, ties broken by region key.
5. **Independence.** Each region is scored only on its own data and fixed references, so excluding or removing a region never changes another region's score. Users can remove suggestions without the rest shifting.
6. **Explanations are templates over the same numbers** (lifestyle/explain.py): a headline, up to three strengths (score ≥ 0.6, by contribution), and caveats (over budget, beyond commute limit, weak spots on attributes weighted ≥ 3, district-rent spread, busy-centre crime statistics). Every sentence quotes its figure and cites a source id.
7. **Persona is rule-based and respectful** (lifestyle/persona.py): the first matching rule over weights and destination type (e.g. "The Campus Explorer"), with the top three priorities. It never uses household, budget or anything that could stand in for a protected characteristic. The UI always asks "Did we get this right?".
8. **No LLM in this feature.** The wording is fixed templates; the product owner agreed to skip Gemini here.

## Evaluation

`make eval-lifestyle` (also run by `pytest`) checks seven scenarios and 27 properties against the shipped data:

- **Definition of Done:** the student preset puts an area ≤ 20 min from TU Berlin with a 30 m² flat ≤ €700 warm in the top 3 (currently Schöneberg Nordwest, 19 min, ≈ €577; Otto-Suhr-Allee/Kantstraße, 15 min, ≈ €678), with reasons.
- Same preset at HTW; family; calm & green; remote/creative; young professional at Potsdamer Platz; night owl. Expectations come from the user's own limits or from the data distribution (e.g. "top quarter of Berlin for bars"), not from region names.
- Properties for every preset: determinism, exclusion invariance, affordable-before-over-budget, grounded explanations (each sentence contains the number it is built from). Monotonicity for seven attributes: raising a weight never pushes down the best region for it.

Two scenario thresholds in the first draft were stricter than the answers implied ("≤ 25 min" when the preset's limit is 30; "2× the Berlin average" for nightlife). They were replaced with the user's own limit and the data's top quartile. The engine was not changed to pass them.

## Alternatives considered

- **Summing answer levels:** rejected. Weights would grow with the number of answers, and order and repetition would matter.
- **Hard filters for budget and commute:** rejected. The product owner prefers showing over-budget areas ranked lower, so users see trade-offs.
- **Live routing per request:** rejected. It would be slow, would differ between environments (the timetable files are not in the production image), and would send a destination through the routing path on every request. The 13 × 143 matrix is small and built once.
- **Free-text destinations:** deferred. A fixed list first; see whether users need more.

## Consequences

- **+** Same answers → same ranking, same explanations; every number traces to ADR-0010 provenance.
- **+** User control: answers, weights and exclusions are all inputs; nothing is stored.
- **−** Commute is only available to the 13 listed destinations.
- **−** The score shapes (70/100/130% of budget; 10 min / limit / 1.5×) are design choices, documented here and covered by tests.
