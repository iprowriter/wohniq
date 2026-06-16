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
- **AC1.** Deterministic signals (price z-score vs. Kiez median, pHash photo duplication, metadata rules) run with no API cost.
- **AC2.** An LLM pass extracts fuzzy text signals (off-platform payment, landlord-abroad, urgency, no-Anmeldung) as validated structured output with evidence quotes.
- **AC3.** Fused score is explainable: output lists the contributing signals with evidence.
- **AC4.** Evaluated against the labeled synthetic set with a reported precision/recall + confusion matrix in the repo.

### F8 — Apartment comparison
Side-by-side comparison of 2–4 selected listings across price, commute, neighborhood, risk, and fit.
- **AC1.** Renders the same structured fields used by ranking and explanation — no recomputation drift.

## 6. User flows

**Primary flow**
1. User enters a natural-language query.
2. Parser → `SearchCriteria` (F1).
3. Retrieval (F2) → candidate set.
4. Ranking (F3) enriched with commute (F5), neighborhood (F6), risk (F7).
5. Results render as cards with explanation (F4) and a risk badge (F7).
6. User opens a listing for detail, or selects several to compare (F8).

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
