# WohnIQ

**AI-assisted apartment search for Berlin.** Describe what you want in plain language — _"I work near Alexanderplatz, budget €1,500, quiet area, good transport, cafes nearby"_ — and WohnIQ parses it, searches, ranks, explains each match, and flags suspicious listings.

> **Portfolio project.** Listings are synthetic by design — intentionally, so we hold ground-truth scam labels for measurable evals (see [ADR-0003](docs/adr/0003-synthetic-data-and-images.md)). The goal is to demonstrate production-grade AI engineering: reliable structured LLM output, clean language-vs-logic separation, a measurable scam detector, tests, evals, and a deployable system.

---

## What this project does

Berlin's rental market is scarce, fast-moving, and scam-prone. Traditional portals show you listings but don't help with the *decision*. WohnIQ's bet: the value isn't fancier filters, it's an AI reasoning layer on top of good data — one that synthesizes commute, neighborhood, budget fit, and risk into an explained recommendation.

**Primary flow:**
1. User types a natural-language query.
2. Gemini Flash parses it into a validated `SearchCriteria` object (budget, rooms, work location, amenities, etc.).
3. Hard constraints filter the listing DB; pgvector cosine search surfaces semantically relevant candidates.
4. A deterministic scoring function ranks results by commute fit, budget fit, neighborhood match, and amenity match.
5. Real-time enrichment fetches public-transport commute times (BVG/VBB API) and POI counts (OSM Overpass).
6. A hybrid scam engine runs on every listing: price z-score, pHash duplicate detection, and an LLM text pass produce a fused 0–100 risk score with evidence.
7. Results render as cards with a natural-language explanation grounded in the score breakdown, a risk badge, and a neighborhood map.
8. Users can select 2–4 listings for a side-by-side comparison.

---

## Key architectural decisions

The architecture reflects a single principle: **LLMs handle language; code handles logic.** Here's how that played out in practice.

### ADR-0001 — Ranking is deterministic; the LLM never scores or orders

The tempting shortcut is to hand the model a list of listings and ask it to rank them. We rejected this: LLMs are inconsistent at ordering, unreliable at arithmetic, and produce opaque reasoning. Instead, ranking is a pure, weighted scoring function in code — same input always produces the same output. The LLM's roles are limited to three single-shot calls: parse a query, read fuzzy scam text, write an explanation from an already-computed breakdown.

This decision is load-bearing for everything else. Because ranking is deterministic, explanations are trustworthy (they're generated *from* the same numbers that produced the rank). Because the LLM is stateless, we don't need an agent framework. [→ ADR-0001](docs/adr/0001-deterministic-ranking.md)

### ADR-0002 — Scam detection is a hybrid rules + pHash + LLM engine

A pure LLM classifier ("is this a scam?") would be opaque, inconsistent, and unconvincing in a demo. Instead, the risk engine fuses three signal sources into an explained 0–100 score:

1. **Deterministic rule signals (€0):** price z-score vs. Kiez+size median; metadata rules (off-platform contact, no-Anmeldung clauses, etc.).
2. **Image signals (local pHash, €0):** perceptual-hash duplicate detection across the listing DB catches reused/stolen photo sets.
3. **LLM text pass (`scam_text.v1`):** extracts fuzzy language signals (urgency, landlord-abroad, payment pressure) as *validated structured output with verbatim evidence quotes* — not a verdict.

The fusion step emits contributing signals with their evidence, so the UI can show exactly *why* a listing was flagged. This "explainable by construction" design is the single best demo screenshot. [→ ADR-0002](docs/adr/0002-hybrid-scam-detection.md)

### ADR-0003 — Synthetic listings with hotlinked stock photos

Real listings drag in legal, privacy, and freshness problems irrelevant to a portfolio project — and, critically, don't give us ground-truth scam labels. We generate ~100 synthetic listings with realistic Berlin distributions (Kieze, rents per m², sizes), including a labeled ~15% scam subset spanning four scam types plus hard negatives (cheap-but-legit, landlord-travels-but-legit). Photos are sourced via the Pexels API by room type and hotlinked (zero storage). The seeder deliberately reuses photo sets across scam listings to create realistic duplicate-photo fraud. [→ ADR-0003](docs/adr/0003-synthetic-data-and-images.md)

### ADR-0004 — Gemini Flash with validated structured output via a central LLM client

Reliability risk with LLMs is not capability but *boundary integrity*: free-form text breaks downstream code. Every Gemini call goes through a central client (`core/llm.py`) that: requests JSON constrained to a Pydantic model, validates the response, re-prompts once on failure, then falls back to a deterministic path (keyword extractor for parsing, rules-only for scam, template for explanation). No unvalidated model text reaches business logic or the user. The client logs prompt id, token counts, latency, and validation result for observability. [→ ADR-0004](docs/adr/0004-gemini-structured-output.md)

### ADR-0005 — Supabase Postgres + pgvector

One free service covering relational data, vector similarity search, and storage. pgvector keeps semantic search inside Postgres — simpler, one query path, credible production story. Cold-start risk (free-tier projects pause after ~1 week) is mitigated by a GitHub Actions cron keep-alive. [→ ADR-0005](docs/adr/0005-supabase-postgres-pgvector.md)

### ADR-0006 — SQLAlchemy 2.0 + Alembic, with raw SQL for vector/ranking queries

Typed `Mapped[...]` models are the single source of truth for the schema; Alembic handles migrations. But the ORM is not used everywhere — pgvector similarity search and ranking queries stay raw SQL (`text()`), because that's where the ORM abstraction fights clarity. Knowing *where not* to use the ORM is part of the decision. [→ ADR-0006](docs/adr/0006-orm-sqlalchemy-alembic.md)

### ADR-0007 — Direct provider SDK over LangChain / LangGraph

WohnIQ's LLM usage is three stateless, single-shot calls. LangGraph is an orchestration framework for stateful, cyclic, multi-actor agent workflows — using it here would be over-engineering. We call the Gemini SDK directly, behind a thin injectable client. Provider portability is achieved by an injectable `transport` boundary in ~10 lines — no framework dependency, readable reliability logic, and easy to swap later. [→ ADR-0007](docs/adr/0007-direct-sdk-over-agent-framework.md)

---

## Stack

| Layer | Tech |
|---|---|
| **Frontend** | Next.js + TypeScript, Tailwind CSS, shadcn/ui, Leaflet + OSM tiles |
| **Backend** | FastAPI, Pydantic, Uvicorn, Docker |
| **AI** | Gemini Flash (`gemini-2.0-flash`) — parsing, scam text, explanations; Gemini `embedding-001` — semantic search |
| **Database** | Supabase Postgres + pgvector |
| **ORM / migrations** | SQLAlchemy 2.0, Alembic |
| **Scam signals** | imagehash (pHash), Pillow |
| **Enrichment** | BVG/VBB `transport.rest` (commute), OSM Overpass (POIs), Nominatim (geocoding) |
| **Images** | Pexels API (hotlinked, attributed in-app) |
| **Deploy** | Backend → Railway (Docker); Frontend → Vercel |
| **Cost** | €0 incremental — Gemini free tier, Supabase free, Railway existing, Vercel free |

---

## Eval results

### Query parser (F1)

Evaluated against 20 canonical queries covering budget-only, location-only, vague vibe queries, and adversarial under-specified inputs.

| Metric | Result |
|---|---|
| Cases fully correct | 20 / 20 (100%) |
| Fields correct | 57 / 57 (100%) |

### Scam detector (F7)

Evaluated against the labeled synthetic set. Precision was the tuning target — avoid crying wolf on cheap-but-legit listings.

| | Predicted scam | Predicted legit |
|---|---|---|
| **Actual scam** | 12 TP | 3 FN |
| **Actual legit** | 2 FP | 83 TN |

| Metric | Result |
|---|---|
| Precision | 86% |
| Recall | 80% |
| F1 | 0.83 |
| Accuracy | 95% |
| Hard negatives cleared | 6 / 8 |

**Recall by scam type:**

| Type | Caught | Recall |
|---|---|---|
| advance_fee | 4 / 4 | 100% |
| overseas_landlord | 4 / 4 | 100% |
| price_bait | 4 / 4 | 100% |
| photo_reuse | 0 / 3 | 0% |

Photo-reuse recall is 0% because pHash matching against hotlinked Pexels URLs requires fetching image bytes, which the test environment does not do. The signal works in production (the seeder fetches bytes at seed time); the eval isolates this as a known gap.

---

## Repo map

| Path | Purpose |
|---|---|
| [`docs/SPEC.md`](docs/SPEC.md) | Product spec — *what* WohnIQ does, features F1–F8, acceptance criteria |
| [`docs/adr/`](docs/adr/) | Architecture decision records — *why* we chose things |
| [`docs/system_prompts.md`](docs/system_prompts.md) | Versioned product LLM prompts (`parser.v1`, `scam_text.v1`, `explain.v1`) |
| [`AGENTS.md`](AGENTS.md) | Operating manual — conventions, golden rules, working loop |
| [`TASKS.md`](TASKS.md) | Ordered task plan with milestone status |
| `backend/core/llm.py` | Central LLM client with validation, retry, fallback, and observability |
| `backend/search/` | Query parser, retrieval (pgvector), deterministic ranking, explanation |
| `backend/scam/` | Rule signals, pHash duplicate detection, LLM text pass, fusion |
| `backend/enrich/` | Commute (BVG/VBB) and neighborhood (OSM) enrichment, both cached |
| `backend/evals/` | Parser eval harness, ranking sanity eval, scam eval + confusion matrix |
| `frontend/` | Next.js app — search box, result cards, risk badge, comparison, Leaflet map |

---

## Quickstart

Backend uses [uv](https://docs.astral.sh/uv/). Install it once: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`).

```bash
# Backend
cd backend
uv sync                       # creates .venv + installs deps
cp ../.env.example ../.env    # fill in GEMINI_API_KEY, DATABASE_URL
uv run alembic upgrade head   # apply schema to Supabase
uv run python -m data.seed_listings
uv run python -m data.seed_images
uv run python -m data.embed_listings
uv run python -m scam.score   # pre-compute risk assessments
uv run uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Evals
cd backend
uv run python -m evals.parser_eval   # or: make eval-parser
uv run python -m evals.ranking_eval  # or: make eval-ranking
uv run python -m evals.scam_eval     # or: make eval-scam
```

From the repo root: `make install`, `make dev`, `make test`, `make lint`.

---

## License / attribution

Apartment photos sourced via the Pexels API; attribution shown in-app per their terms.
