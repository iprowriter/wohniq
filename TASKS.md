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

➡️ **T4.4 — Comparison tool (F8).** (T4.3 done. Side-by-side of 2–4 listings using the shared structured fields.)

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
- [x] **T3.5 — Scam eval + confusion matrix.** `evals/metrics.py` (pure: confusion/precision/recall/F1/recall-by-group) + `scam/detector.py` (`assess_listing` orchestration) + `evals/scam_eval.py` (`make eval-scam`, writes JSON + Markdown, per-type recall + hard-negative clearance). Metrics + detector unit-tested. _AC: SPEC F7 AC4. Depends: T3.4_

## M4 — Depth
- [x] **T4.1 — Commute analysis (F5).** `enrich/commute_parse.py` (pure journey→minutes/changes/walk) + `enrich/commute.py` (keyless BVG/VBB transport.rest client, `commute_cache`, graceful degrade). Parser unit-tested. _AC: SPEC F5. Depends: T1.3_
- [x] **T4.2 — Neighborhood insights (F6).** `enrich/neighborhood_parse.py` (pure: Overpass query, parse → counts + per-POI list w/ coords + available set + summary) + `enrich/neighborhood.py` (Overpass client + cache). `pois` column added (migration 0002) for a future map. Parser unit-tested. _AC: SPEC F6. Depends: T1.3_
- [x] **T4.3 — Enrich ranking.** `/search` now enriches top-k with `get_commute` + `get_neighborhood`, re-ranks (commute + amenity factors active), and returns commute + neighborhood per result. Endpoint test updated. _Depends: T2.5, T4.1, T4.2_
- [ ] **T4.4 — Comparison tool (F8).** Side-by-side of 2–4 listings using the shared structured fields. _AC: SPEC F8. Depends: T2.7, T3.4_

## M5 — Polish & deploy
- [ ] **T5.1 — Frontend.** Next.js: search box, result cards (explanation + risk badge), detail page, comparison, Leaflet map. _Depends: T2.8_
- [ ] **T5.2 — Deploy.** Backend → Railway (Docker); frontend → Vercel; env/secrets wired. _Depends: T5.1, T1.2_
- [ ] **T5.3 — Observability pass.** Confirm every LLM call logs id/version/tokens/latency/validation (SPEC §8). _Depends: T2.8, T3.4_
- [ ] **T5.4 — README story.** Spec → decisions → evals → results, with synthetic-data note and confusion matrix. _Depends: T3.5_

---

## Notes
- Re-point **Current next step** whenever a task completes.
- Skills (`SKILL.md`) and per-feature instructions get written *just-in-time* — skills once a workflow proves repeatable (e.g. T1.4/T1.5, T3.x), feature instructions at the head of each milestone. Not now.
