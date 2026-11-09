# WohnIQ — Task Plan

> The durable backlog. This file answers one question: **what is the next exact step?**
> Derived from `docs/SPEC.md` (features F1–F8, milestones M0–M5) and constrained by `docs/adr/` and `AGENTS.md`.
> This is the *plan of record* (committed to git, survives sessions). The live in-session checklist is separate and ephemeral.

## How to use this file

1. **Next step = the top unchecked task whose dependencies are all checked.** Don't skip ahead.
2. Before starting a task, open its **AC** (acceptance criterion) in `docs/SPEC.md` — that's the "done" test.
3. If a task forces an architecture change, **write an ADR first**, then continue.
4. Work the loop in `AGENTS.md`: write the test/eval → implement the smallest change → run tests + lint → read the diff → commit.
5. Check the box only when the AC passes. Partial work stays unchecked.

## Status legend

`[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked (note why)

---

## Current next step

➡️ **T1.2 — CI + Supabase keep-alive.** (M0–M5 shipped and live at https://wohniq-plum.vercel.app. Close out the last open foundation task, then start M6 — see [`ROADMAP.md`](ROADMAP.md).)

---

## M0 — Foundation
- [x] T0.1 — Write `docs/SPEC.md`
- [x] T0.2 — Write `AGENTS.md`
- [x] T0.3 — Write `docs/system_prompts.md`
- [x] T0.4 — Write ADRs 0001–0005
- [x] T0.5 — Write `TASKS.md` (this file)

## M1 — Data foundation
*Everything downstream needs listings to exist. Build data first.*
- [x] **T1.1 — Repo scaffolding.** `backend/` + `frontend/` skeletons, `.gitignore`, `README.md`, `pyproject` (deps + Ruff/Black/pytest config), `.env.example`, `Makefile`, health endpoint + smoke test. _Depends: —_
- [ ] **T1.2 — CI + Supabase keep-alive.** GitHub Actions: lint+test on push; cron ping to keep Supabase warm (ADR-0005). _Depends: T1.1_
- [x] **T1.3 — DB schema + migrations.** SQLAlchemy 2.0 models (`data/models.py`) for all 6 tables (SPEC §7) + Alembic (ADR-0006); initial revision `0001_initial_schema`. pgvector enabled; `core/db.py` engine/session. _Depends: T1.1_
- [x] **T1.4 — Synthetic listing generator.** Pure stdlib generator (`data/synthetic.py`) + Kiez data (`data/kieze.py`) + DB seeder (`data/seed_listings.py`) + label manifest. Balanced 15% scams across 4 types, 8 hard negatives. Unit-tested (`tests/test_synthetic.py`). _Depends: T1.3_
- [x] **T1.5 — Image seeder (`seed_images.py`).** Pexels client + pure assignment (`photo_assign.py`) + pHash (`imaging.py`); 5 coherent photos/listing, cached pool, duplicate sets via shared photo_set_id. Unit-tested. _Depends: T1.3_
- [x] **T1.6 — Embedding backfill.** Gemini embeddings client (`core/embeddings.py`, asymmetric task types, batched) + pure text builder (`data/embed_text.py`) + idempotent backfill (`data/embed_listings.py`) into pgvector. Unit-tested. _Depends: T1.4_

## M2 — Core spine (search end-to-end)
*The headline demo: query → parsed → retrieved → ranked → explained.*
- [x] **T2.1 — Central LLM client.** `core/llm.py`: structured-output Gemini call, Pydantic validation, one re-prompt, caller fallback, observability logging. Injectable transport → unit-tested without network. _Depends: T1.1_
- [x] **T2.2 — Query parser (F1).** `parser.v1` → `SearchCriteria` via the LLM client. `search/criteria.py` (schema + canonical-amenity validator), `search/parse_rules.py` (pure keyword fallback), `search/parser.py`. Unit-tested. _AC: SPEC F1. Depends: T2.1_
- [x] **T2.3 — Parser eval harness.** `evals/` package: 20 canonical cases (`parser_cases.py`), pure scorer (`scoring.py`), runner with report + threshold gate (`parser_eval.py`, `make eval-parser`). Scorer unit-tested. _Depends: T2.2_
- [x] **T2.4 — Retrieval (F2).** `search/filters.py` (pure hard-filter spec) + `search/retrieval.py` (filters + pgvector cosine search via typed expression). Filter + mapping unit-tested. _AC: SPEC F2. Depends: T1.6, T2.2_
- [x] **T2.5 — Deterministic ranking (F3).** `search/ranking.py`: pure weighted scorer (relevance/budget/commute/quiet/amenities), per-factor breakdown, configurable `RankingWeights`, stable sort. Fully unit-tested (8 tests, verified offline). _AC: SPEC F3. Depends: T2.4_
- [x] **T2.6 — Ranking sanity eval.** `evals/ranking_cases.py` (5 designed scenarios) + `evals/ranking_eval.py` (`make eval-ranking`). Pure/offline → runs in CI as a weight-regression guard. All 5 pass (verified). _Depends: T2.5_
- [x] **T2.7 — Explanation layer (F4).** `search/explanation.py` (`explain.v1` from the breakdown + deterministic template fallback) + `search/explain_rules.py` (pure reason/caveat selection). Unit-tested. _AC: SPEC F4. Depends: T2.5_
- [x] **T2.8 — `/search` API endpoint.** `app/routers/search.py`: POST `/api/v1/search` runs parse→retrieve→rank→explain, returns criteria + ranked results (listing, score, factor breakdown, explanation, photos). `is_scam`/`scam_type` never serialized. Wiring test w/ overrides. _Depends: T2.7_

## M3 — Showpiece (scam detection)
- [x] **T3.1 — Deterministic signals.** `scam/signals.py`: shared `Signal` shape, Kiez price stats (median/MAD), price-below-market (% + robust z) and no-Anmeldung rules. Pure, unit-tested. _AC: SPEC F7 AC1. Depends: T1.4_
- [x] **T3.2 — Image duplicate signal.** `scam/photo_dups.py`: pure hex Hamming + cross-listing duplicate detection → `photo_reuse` Signal (severity scales with matched photos). Unit-tested. _AC: SPEC F7 AC1. Depends: T1.5_
- [x] **T3.3 — Scam text pass.** `scam/text_signals.py`: `scam_text.v1` → `ScamTextSignals` (5 signals w/ quotes + confidence) via LLM client, empty fallback, `to_signals()` → shared Signal list (source="llm"). Unit-tested. _AC: SPEC F7 AC2. Depends: T2.1_
- [x] **T3.4 — Risk fusion.** `scam/fusion.py`: weighted noisy-OR of signals → 0–100 score + Low/Caution/High band + contributing signals. Photo-reuse-alone capped at Caution. Pure, unit-tested. _AC: SPEC F7 AC3. Depends: T3.1, T3.2, T3.3_
- [x] **T3.6 — Persist risk + expose in API.** `scam/score.py` (`make score`) batch-writes `risk_assessment`; `/search` + `/compare` read it and return `risk` (band/score/signals) — single stored source, no drift. _Depends: T3.4_
- [x] **T3.5 — Scam eval + confusion matrix.** `evals/metrics.py` (pure: confusion/precision/recall/F1/recall-by-group) + `scam/detector.py` (`assess_listing` orchestration) + `evals/scam_eval.py` (`make eval-scam`, writes JSON + Markdown, per-type recall + hard-negative clearance). Metrics + detector unit-tested. _AC: SPEC F7 AC4. Depends: T3.4_

## M4 — Depth
- [x] **T4.1 — Commute analysis (F5).** `enrich/commute_parse.py` (pure journey→minutes/changes/walk) + `enrich/commute.py` (keyless BVG/VBB transport.rest client, `commute_cache`, graceful degrade). Parser unit-tested. _AC: SPEC F5. Depends: T1.3_
- [x] **T4.2 — Neighborhood insights (F6).** `enrich/neighborhood_parse.py` (pure: Overpass query, parse → counts + per-POI list w/ coords + available set + summary) + `enrich/neighborhood.py` (Overpass client + cache). `pois` column added (migration 0002) for a future map. Parser unit-tested. _AC: SPEC F6. Depends: T1.3_
- [x] **T4.3 — Enrich ranking.** `/search` now enriches top-k with `get_commute` + `get_neighborhood`, re-ranks (commute + amenity factors active), and returns commute + neighborhood per result. Endpoint test updated. _Depends: T2.5, T4.1, T4.2_
- [x] **T4.4 — Comparison tool (F8).** `POST /api/v1/compare` for 2–4 listings, reusing the exact search helpers (listing/commute/neighborhood/fit/explanation) — no recomputation drift. Endpoint test (order, fit, 422/404, label-leak). _AC: SPEC F8. Depends: T2.7, T3.4_

## M5 — Polish & deploy
- [x] **T5.1 — Frontend.** Next.js: search box, criteria chips, result cards (explanation + risk badge), listing detail page, comparison modal, Leaflet neighborhood map. _Depends: T2.8_
- [x] **T5.2 — Deploy.** Backend → Railway (`backend/Dockerfile`, `backend/railway.toml`); frontend → Vercel; env/secrets wired. Live. _Depends: T5.1_ (CI from T1.2 still to add.)
- [x] **T5.3 — Observability pass.** Confirm every LLM call logs id/version/tokens/latency/validation (SPEC §8). _Depends: T2.8, T3.4_
- [x] **T5.4 — README story.** Spec → decisions → evals → results, with synthetic-data note and confusion matrix. _Depends: T3.5_


## M6 — Next iteration
*Planned product work. Details, scope and estimates in [`ROADMAP.md`](ROADMAP.md).*
- [ ] **T6.1 — Fix photo-reuse detection.** Store pHash at seed time; scam eval reads stored hashes (current recall 0/3). _Depends: T3.2_
- [ ] **T6.2 — German-language queries.** Parser accepts German input; DE/EN UI toggle. _Depends: T2.2_
- [ ] **T6.3 — Shareable searches.** Query + filters in the URL; recent searches in localStorage (no accounts). _Depends: T5.1_
- [ ] **T6.4 — Results map view.** All ranked results on one Leaflet map, synced with the list. _Depends: T5.1_
- [ ] **T6.5 — Multi-destination commute.** Up to 2 work/study locations + departure time. _Depends: T4.1_
- [ ] **T6.6 — Cold-start & error UX.** Loading, retry and error states for a sleeping backend or failed enrichment. _Depends: T5.1_
- [ ] **T6.7 — Mobile & accessibility pass.** Responsive cards/compare, keyboard nav, contrast, screen-reader labels. _Depends: T5.1_
- [ ] **T6.8 — Frontend tests.** Playwright smoke: search → results → detail → compare, run in CI. _Depends: T1.2_
- [ ] **T6.9 — Model & prompt upkeep.** Move off `gemini-2.0-flash`, bump prompt versions, re-run evals as regression check. _Depends: T2.3_

## M7 — Lifestyle Match
*Questionnaire → weights → deterministic ranking of Berlin regions, with sourced explanations. Stateless and never logged. [ADR-0010](docs/adr/0010-lifestyle-match-data-model.md).*
- [x] **T7.1 — Data model & region profiles.** 143 LOR Bezirksregionen from the Kriminalitätsatlas (safety), Einwohnerregister (family, young crowd), LOR 2021 geometry (centres, area, density) and Umweltgerechtigkeitsatlas (quiet, clean air, cooler summers, green); source registry with caveats; fixed normalisation; `make lifestyle-data` (reproducible, input SHA-256s recorded; `make test-all` re-verifies). Tests: `test_lifestyle_profiles.py`, `test_lifestyle_build.py`.
- [x] **T7.1b — Amenity, transit & rent data.** OSM GeoPackage → cafés, everyday, nightlife, culture, sport, water (measured from 100 m grid points on residential land); VBB GTFS peak network → transit; IBB Tabellenband Tab. 25 → district rents. Tests: `test_lifestyle_access.py`. _Depends: T7.1_
- [x] **T7.2 — Scoring engine.** `lifestyle/questionnaire.py` (10 bounded questions, 5 presets), `weights.py` (max-level mapping + overrides), `scoring.py` (weights × profiles; affordability + precomputed commute to 13 fixed destinations; lexicographic budget/commute ranking), `explain.py` (grounded templates), `persona.py`. [ADR-0011](docs/adr/0011-lifestyle-match-scoring.md). Tests: `test_lifestyle_engine.py`. _Depends: T7.1_
- [x] **T7.3 — API + privacy.** `app/routers/lifestyle.py`: `GET /catalog`, `GET /regions.geojson` (143 simplified outlines, 5 m), `POST /profile`, `POST /match`, `POST /listings` (listings matched to regions by coordinates). Stateless, no-store, counts-only logging; `/search`, commute-failure and LLM-validation logs redacted. [ADR-0012](docs/adr/0012-privacy-by-design.md). Tests: `test_lifestyle_api.py`, `test_lifestyle_privacy.py`. _Depends: T7.2_
- [x] **T7.4 — Questionnaire UI.** `/lifestyle`: welcome + 5 preset cards + "start from scratch", 4 catalog-driven pages (progress bar, back/next, jump to visited steps), summary with persona, weights-with-reasons and "You told us" (each answer editable), "Clear my answers". Answers in sessionStorage only. Pure logic in `lib/lifestyle/logic.ts`; `npm test` (node --test, 20 tests incl. a contract test against the backend catalog fixture, `make lifestyle-fixture`). Verified in headless Chromium: keyboard flow, no horizontal overflow on desktop/mobile, no console errors. _Depends: T7.3_
- [x] **T7.5 — Results UI.** `/lifestyle/results`: ranked area cards (score ring, budget/commute badges, reasons with source chips, trade-offs; "Why this score" factor bars; "The data behind this" with sources + data notes), shaded Leaflet map of all 143 areas with numbered top matches (card ↔ map selection, "All of Berlin"), "Tune your match" sliders with reasons and an explicit **Update results** button, "Not for me" + undo, "Show more", listings side panel (coordinates-matched, risk badges, empty state). `/match` now also returns compact `scores` for every region; explanations split into `caveats` (trade-offs) and `notes` (data caveats). Tests: `tests/lifestyle-results.test.ts`; headless-browser walkthrough (map 143 outlines + 10 markers, exclude/undo, update, panel focus/Esc, no overflow). _Depends: T7.4_
- [x] **T7.6 — Homepage entry + marketing card.** Glowing "Try Lifestyle Match" bar under the hero search box; full-width marketing card above the two existing feature cards (facts checked against the catalog by `tests/lifestyle-marketing.test.ts`; decorative, data-free preview); "Lifestyle Match" link in header (with "new" dot) and footer. Verified in headless Chromium on desktop/mobile: links, keyboard, no overflow. _Depends: T7.5_
- [x] **T7.7 — Evals, end-to-end tests & docs.** `make eval-lifestyle` 38/38 (7 scenarios incl. the Definition of Done; determinism, exclusion invariance, budget ordering, groundedness, monotonicity, privacy by construction); log-leak tests; Playwright journeys (`frontend/e2e/`, desktop + mobile, `npm run test:e2e`); `backend/.dockerignore` (raw data + secrets out of the image; runtime verified without build-only deps); final privacy sweep; [`docs/LIFESTYLE_MATCH.md`](docs/LIFESTYLE_MATCH.md) with the DoD checklist, README section + screenshots, SPEC F9, ROADMAP. _Depends: T7.2_

---

## Notes
- Re-point **Current next step** whenever a task completes.
- Skills (`SKILL.md`) and per-feature instructions get written *just-in-time* — skills once a workflow proves repeatable (e.g. T1.4/T1.5, T3.x), feature instructions at the head of each milestone. Not now.
