# WohnIQ — Product Specification (PRD)

> **Status:** Draft v0.1 · **Owner:** Martin · **Last updated:** 2026-06-15
> This is the source of truth for *what* WohnIQ does. Architecture and *how* decisions live in `docs/adr/`. Product LLM prompts live in `docs/system_prompts.md`.

---

## 1. Summary

WohnIQ is an AI-assisted apartment-search platform for Berlin. Instead of clicking filters, users describe what they want in natural language ("I work near Alexanderplatz, budget €1,500, quiet area, good transport, cafes nearby"). An LLM converts the request into structured criteria; a deterministic engine searches and ranks listings; an AI layer explains *why* each result fits and flags suspicious listings.

The product is a **portfolio project**, not a startup. It uses realistic **synthetic listings** with hotlinked stock photos. The goal is to demonstrate production-grade AI engineering: reliable structured LLM output, a clean separation of language vs. logic, measurable AI quality (evals), and a polished, deployable system.

## 2. Problem

Berlin's rental market is scarce, fast-moving, and scam-prone. Searchers — many of them expats operating in a second language — juggle five browser tabs to answer questions the listing pages don't: *How long is the commute? Is this Kiez quiet? Are there cafes? Is this price too good to be true?* Traditional filter-based portals surface listings but don't help with the **decision**.

WohnIQ's bet: the value isn't fancier search, it's an **AI reasoning layer on top of good data** that synthesizes commute, neighborhood, budget fit, and risk into an explained recommendation.

## 3. Target users

- **Primary:** Newcomers/expats moving to Berlin, searching in English, unfamiliar with Kieze and rental norms (Kaltmiete/Warmmiete, Kaution, Anmeldung, SCHUFA).
- **Secondary:** Existing Berlin residents relocating within the city who want commute- and neighborhood-aware ranking.

## 4. Goals & non-goals

**Goals**
- Natural-language query → structured criteria with high reliability.
- Deterministic, inspectable ranking with transparent scoring.
- Trustworthy explanations grounded in concrete evidence.
- A standout, *measurable* scam/risk detector (the showpiece).
- Production-grade engineering: tests, evals, CI, observability, deployable.

**Non-goals**
- Not a chatbot. Conversation is an input method, not the product.
- Not real-time/real listings. Data is synthetic by design (see ADR-0003).
- No payments, no landlord onboarding, no messaging between parties.
- No mobile app (responsive web only).
- No multi-city support. Berlin only.

## 5. Features & acceptance criteria

Each feature lists acceptance criteria (AC) used as the "done" test for its task(s).

### F1 — Natural-language query parsing
Convert free-text into a validated `SearchCriteria` object (budget, rooms, size, work location, transport priority, quiet preference, desired amenities, etc.).
- **AC1.** Returns a schema-valid `SearchCriteria` for the 20 canonical eval queries.
- **AC2.** Ambiguous/under-specified queries ("somewhere I can bike to work, not too loud") populate the fields they can and leave others null — never hallucinates a budget.
- **AC3.** On invalid/garbage model output, the parser falls back gracefully (re-prompt once, then a deterministic keyword extractor) and never 500s.

### F2 — Apartment search & retrieval
Query the listing DB using parsed criteria + semantic similarity (pgvector).
- **AC1.** Hard constraints (budget ceiling, min rooms) are respected as filters, not soft signals.
- **AC2.** Semantic ranking returns relevant results for vibe queries with no exact keyword match.
- **AC3.** Returns within the documented latency budget (see §8) for a 100-listing DB.

### F3 — Deterministic ranking engine
Score and order listings with a transparent, inspectable function (commute fit, budget fit, neighborhood match, amenity match).
- **AC1.** Ranking is reproducible: same input → same order. No LLM in the ranking path (see ADR-0001).
- **AC2.** Every result carries its per-factor score breakdown.
- **AC3.** Weights are configurable and documented.

### F4 — AI explanation layer
For each ranked result, produce a short natural-language rationale grounded in its scores.
- **AC1.** Every claim in the explanation maps to a real data point (commute minutes, € delta, amenity count) — no invented facts.
- **AC2.** Explanations are generated from the structured score breakdown, not free-form over raw listings.

### F5 — Commute analysis
Compute public-transport travel time from each listing to the user's work location.
- **AC1.** Uses the free BVG/VBB transit API; results cached per (origin, destination).
- **AC2.** Returns door-to-door minutes + number of changes; degrades gracefully if the API is unavailable.

### F6 — Neighborhood insights
Summarize each listing's Kiez: cafes, parks, supermarkets, nightlife, transport.
- **AC1.** POI counts sourced from OSM Overpass within a fixed radius; cached per location.
- **AC2.** A short qualitative summary ("quiet, residential, well-served by U2") derived from the counts.

### F7 — Scam / risk detection *(showpiece)*
Hybrid engine producing an explained 0–100 risk score and Low/Caution/High band per listing. See ADR-0002.
- **AC1.** Deterministic signals (price vs. the Mietspiegel's lowest value for the flat, falling back to the Kiez median; pHash photo duplication with at least 4 photos shared with one listing; metadata rules) run with no API cost. See ADR-0017.
- **AC2.** An offline wording check (English/German, negation-aware; ADR-0018) catches the classic phrases without an API; an LLM pass extracts fuzzy text signals (off-platform payment, landlord-abroad, urgency, no-Anmeldung) as validated structured output with evidence quotes.
- **AC3.** Fused score is explainable: output lists the contributing signals with evidence.
- **AC4.** Evaluated against the labeled synthetic set with a reported precision/recall + confusion matrix in the repo.

### F8 — Apartment comparison
Side-by-side comparison of 2–4 selected listings across price, commute, neighborhood, risk, and fit.
- **AC1.** Renders the same structured fields used by ranking and explanation — no recomputation drift.

### F9 — Lifestyle Match
A multi-step questionnaire (or preset) → lifestyle persona → ranked Berlin areas, explained with the data behind them. See [`LIFESTYLE_MATCH.md`](LIFESTYLE_MATCH.md) and ADR-0010/0011/0012.
- **AC1.** Users can go back and change any answer; the summary shows their choices and a predicted persona and asks them to confirm before matching.
- **AC2.** Ranking is deterministic: answers → 0–5 weights (documented mapping) × fixed-reference area scores. No LLM in the path; removing an area never changes another area's score.
- **AC3.** Every suggestion lists its reasons, each quoting a figure and citing its source publication; data caveats are shown alongside.
- **AC4.** Users can adjust weights, remove areas (with undo) and explicitly update the results; over-budget areas are shown but ranked lower.
- **AC5.** Privacy by design: answers are fixed choices (no free text), never stored in the database, never logged, and never put in URLs, cookies or localStorage.
- **AC6 (Definition of Done).** With the Student preset, the top results include an area near TU Berlin where a typical flat fits the student budget, with reasons — and the answers are not stored or logged.

### F10 — Berlin Neighborhoods
All 143 Berlin areas as a ranked list next to an OSM map, re-rankable by category. See [`NEIGHBORHOODS.md`](NEIGHBORHOODS.md) and ADR-0013.
- **AC1.** A "Berlin Neighborhoods" menu entry opens `/neighborhoods`: the list on one side (below on mobile), the map on the other (above on mobile).
- **AC2.** Clicking an area on the map selects it in the sidebar (scrolls to it and expands its detail); selecting a row highlights the area on the map.
- **AC3.** Areas are ranked Berlin-wide; a category switcher (crime, road safety, affluence, education, healthcare, amenities, parks, transport, environment, parking, affordability, weighted overall) re-ranks the list and recolours the map; best-first / worst-first.
- **AC4.** Every figure cites its source, period and method; category caveats are shown; missing data is marked pending, never scored as zero.
- **AC5.** Deterministic, no LLM; labels describe the measure, never the residents; no "avoid" wording.

### F11 — Rent check
Every listing and any Berlin address checked against the Berliner Mietspiegel 2026 and the rent brake. See ADR-0016/0017.
- **AC1.** A listing shows the index range, the rent-brake limit (index mean + 10 %, labelled an estimate) and a verdict: within the limit, above it (with € per m² and per month), below the index, or a new build without a limit.
- **AC2.** For any of the 400,505 residential addresses, the user enters size, building age and cold rent, optionally an energy value and the official checklist; the result follows the brochure's method (its worked example, €7.30 → €7.75, is a test).
- **AC3.** The flat's rent and features are computed in the browser and never sent to the server or put in a URL.
- **AC4.** The rent-brake exemptions and "not legal advice" are shown with every verdict; every figure cites the Mietspiegel row.
- **AC5.** Works offline (demo mode) and live (Supabase) with the same answers.

### F12 — Around this flat & Right now
- **AC1.** For any point: nearest S/U-Bahn (walking minutes), schools within 1 km, Kitas and places within 500 m, nearest park ≥ 1 ha and playgrounds, air quality at the nearest station, road accidents within 300 m, recorded crime for the district region, and the location class — each with its source and its position among Berlin's 542 planning areas (crime: 143 regions).
- **AC2.** Wording describes and never judges ("closer than", "more than in", "higher than in"); no area is coloured or ranked by who lives there.
- **AC3.** A listing's street, planning area, rent check and profile all come from the same matched address.
- **AC4.** Right now always lists the six nearest stops with transport types and walking minutes, without a network; with one, live departures at the nearest S/U-Bahn station and bus/tram stop, labelled live.

## 6. User flows

**Primary flow**
1. User enters a natural-language query.
2. Parser → `SearchCriteria` (F1).
3. Retrieval (F2) → candidate set.
4. Ranking (F3) enriched with commute (F5), neighborhood (F6), risk (F7).
5. Results render as cards with explanation (F4) and a risk badge (F7).
6. User opens a listing for detail, or selects several to compare (F8).

**Lifestyle Match flow (F9)**
1. Homepage entry bar / card → `/lifestyle`: pick a preset or start from scratch.
2. Four question pages → summary with persona → "Yes, that's me".
3. `/lifestyle/results`: ranked areas with reasons and sources, shaded map, tune weights → Update results, remove areas.
4. "See flats here" → WohnIQ listings located in the area (with risk badges) → listing detail.

**Berlin Neighborhoods flow (F10)**
1. Header menu "Berlin Neighborhoods" → `/neighborhoods`: overall ranking, list + map.
2. Pick a category (e.g. Safety) → re-ranked list and recoloured map; toggle best-first / worst-first.
3. Click an area on the map (or a row) → its detail: strengths, watch-outs, metrics vs. Berlin with sources, rank in every category.
4. Optional: adjust weights → Update ranking; share the URL.

## 7. Data model (high level)

Authoritative schema lives in code/migrations; this is the conceptual sketch.
- **listing**: id, title, description, address, kiez, lat/lng, rooms, size_m2, kaltmiete, warmmiete, deposit, furnished, available_from, contact_blob, photo_set_id, is_synthetic, scam_label (ground truth, hidden from UI).
- **photo**: id, photo_set_id, source_url, room_type, phash, attribution.
- **listing_embedding**: listing_id, vector (pgvector).
- **neighborhood_cache**: location_key, poi_counts, summary, fetched_at.
- **commute_cache**: origin_key, dest_key, minutes, changes, fetched_at.
- **risk_assessment**: listing_id, score, band, signals[], created_at.

## 8. Non-functional requirements

- **Cost:** €0 incremental. Reuse Gemini (free tier) + Railway (existing). Supabase free, Vercel free. See ADR-0003/0004.
- **Latency target:** search→ranked results < ~3s p95 on the 100-listing dataset (excludes cold transit/POI fetches, which are cached).
- **Reliability:** every LLM call is schema-validated with a fallback; no user-facing 500 from a bad model response.
- **Observability:** every LLM call logs prompt id/version, token counts, latency, validation pass/fail.
- **Reproducibility:** dockerized backend; seedable DB; deterministic ranking.

## 9. Success metrics (portfolio-grade)

- Parser eval: ≥ 90% schema-valid + field-correct on the 20 canonical queries.
- Scam detector: reported precision/recall + confusion matrix on the labeled set; precision prioritized (don't cry wolf on legit cheap flats).
- Ranking: sanity eval — a basket of queries returns the hand-labeled "should be top 5" listing in the top 5.
- Lifestyle Match: scenario + property eval (`make eval-lifestyle`) passes 100%, including the Definition of Done scenario; privacy tests prove answers never reach logs.
- Repo quality: green CI, tests passing, README that tells the spec→decisions→evals story.

## 10. Open questions

- Do we expose user accounts/saved searches (Supabase Auth), or keep it stateless for v1?
- Comparison tool: 2–4 listings — fixed cap or dynamic?
- Do we ship a "why not" (negative) explanation for low-ranked listings, or only positives?

## 11. Milestones

1. **M0 — Foundation:** spec, AGENTS.md, ADRs, system prompts (this scaffold).
2. **M1 — Data:** schema + migrations, synthetic listing generator, image seeding, embeddings.
3. **M2 — Core spine:** parser (F1) → retrieval (F2) → ranking (F3) → explanation (F4), end to end.
4. **M3 — Showpiece:** scam detection (F7) + eval harness + confusion matrix.
5. **M4 — Depth:** commute (F5), neighborhood (F6), comparison (F8).
6. **M5 — Polish:** frontend, deploy, README, observability, CI.
