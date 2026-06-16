# AGENTS.md — WohnIQ

> The operating manual for any AI agent (or human) working in this repo. Read this first, every session.
> Filename note: `AGENTS.md` is the cross-tool convention (Claude Code, Cursor, etc. also read `CLAUDE.md` — symlink if needed). This is the single source of truth for *how we work here*. *What* we build is in `docs/SPEC.md`; *why* we chose things is in `docs/adr/`.

## What this project is

WohnIQ — an AI-assisted Berlin apartment search. **Portfolio project, not a startup.** Data is synthetic by design. The point is to demonstrate production-grade AI engineering, so quality bars (tests, evals, types, observability) are not optional.

## Golden rules (do not violate without an ADR)

1. **LLMs handle language; code handles logic.** The model parses queries, reads fuzzy text, and writes explanations. It must NEVER rank, score, do math, or order results. Ranking is a deterministic function. (ADR-0001)
2. **Every LLM call returns validated structured output.** All Gemini calls go through the Pydantic-validated layer with a defined fallback. No raw, unparsed model text reaches business logic or the user. (ADR-0004)
3. **No invented facts in explanations.** Explanations are generated from the structured score breakdown. Every claim must trace to a real data point.
4. **Scam scoring is hybrid and explainable.** Deterministic signals + one LLM text pass, fused into a score that lists its contributing signals with evidence. Never "ask the LLM if it's a scam." (ADR-0002)
5. **Cost stays at €0 incremental.** Reuse Gemini (free tier) and Railway. No new paid services. Prefer free APIs (BVG/VBB transit, OSM Overpass, Nominatim, Pexels). (ADR-0003)
6. **Secrets never touch git.** Keys live in env vars / `.env` (gitignored). The Gemini key in particular.

## Stack (see docs/STACK or SPEC §8 for rationale)

- **Frontend:** Next.js (React + TypeScript), Tailwind + shadcn/ui, Leaflet + OSM tiles, TanStack Query. Deploy: Vercel (free).
- **Backend:** FastAPI (Python), Pydantic, Uvicorn. Deploy: Railway. Containerized with Docker.
- **AI:** Gemini API (Flash) for parsing/scam-text/explanations; Gemini embeddings for search. Structured output via Pydantic + function-calling.
- **Data:** Supabase Postgres + pgvector + Storage + (optional) Auth.
- **External (free):** BVG/VBB `transport.rest` (commute), OSM Overpass (POIs), Nominatim (geocoding), Pexels/Unsplash (images).
- **Scam ML (local):** imagehash (pHash), Pillow, NumPy/pandas, optional scikit-learn.

## Repository layout (target)

```
wohniq/
├── AGENTS.md                 # this file
├── README.md                 # the story: spec → decisions → evals → results
├── docs/
│   ├── SPEC.md               # product spec / PRD (source of truth for WHAT)
│   ├── system_prompts.md     # versioned product LLM prompts + schemas
│   └── adr/                  # architecture decision records (WHY)
├── backend/
│   ├── app/                  # FastAPI app, routers
│   ├── core/                 # config, logging, llm client + validation layer
│   ├── search/               # retrieval + ranking (deterministic)
│   ├── scam/                 # rules, phash, llm pass, fusion
│   ├── enrich/               # commute + neighborhood clients (cached)
│   ├── data/                 # synthetic generators, seeders, migrations
│   └── tests/                # pytest: unit + AI eval harness
├── frontend/                 # Next.js app
└── .github/workflows/        # CI: lint + test; cron keep-alive for Supabase
```

## Conventions

- **Python:** type-hinted everywhere. Format with Black, lint with Ruff. Pydantic models for all I/O boundaries.
- **TypeScript:** strict mode. ESLint + Prettier.
- **Commits:** small and meaningful, imperative mood ("Add price z-score signal"). One logical change per commit.
- **Branches/PRs:** feature branches; PRs reviewed (diff read by a human) before merge. CI must be green.
- **Prompts:** every product prompt is versioned in `docs/system_prompts.md` with an id (e.g. `parser.v1`). Code references the id; never inline a divergent copy.
- **No new dependency** without a one-line justification in the PR description.

## Commands (fill in as the repo grows)

Backend is managed with **uv**: `uv sync` builds `.venv` from `pyproject.toml` + `uv.lock`; `uv run <cmd>` runs inside it (no manual activation). The `uv.lock` file is committed for reproducibility.

```bash
# Backend (or use the Makefile targets from repo root)
cd backend && uv sync                             # install deps (incl. dev group)
uv run uvicorn app.main:app --reload              # run API
uv run pytest                                     # run tests + evals
uv run ruff check . && uv run black --check .     # lint/format

# Frontend
cd frontend && npm run dev                        # run UI
npm run lint                                      # lint

# Data
cd backend && uv run alembic upgrade head         # apply DB migrations (or: make migrate)
uv run python -m data.seed_listings               # generate synthetic listings
uv run python -m data.seed_images                 # assign Pexels photos (incl. scam dupes)
```

Schema is **SQLAlchemy 2.0 models** (`backend/data/models.py`) — the single source of truth — with **Alembic** migrations in `backend/data/migrations/` (ADR-0006). Change the models, then `uv run alembic revision --autogenerate -m "..."`, review the generated file, and `alembic upgrade head`. Never edit an applied revision. **Rule of thumb:** ORM for CRUD; raw SQL (`text()`) for the pgvector search and ranking queries.

**Migration guardrails (these are hard rules — a near-miss already happened):**

1. **One database per project.** WohnIQ gets its own dedicated database, never one shared with another project. Alembic autogenerate treats the models as the *complete* description of the DB, so any table it doesn't know about (e.g. another project's) gets a `drop_table` in the generated migration. Confirm `DATABASE_URL` points at the WohnIQ DB before running anything.
2. **Always read an autogenerated migration before applying it.** `--autogenerate` writes `drop_table`/`drop_column` for anything in the DB but not in the models — it is destructive by default. Open the generated `versions/*.py`, confirm it only does what you intended, and delete it if it proposes dropping tables you didn't mean to touch. Generating a migration changes nothing; `upgrade head` is the irreversible step.
3. **Use the `postgresql+psycopg://` driver.** Config coerces this automatically via `settings.sqlalchemy_url`; don't hand-build engines off the raw `DATABASE_URL` (plain `postgresql://` defaults to psycopg2, which isn't installed).

**Embedding ↔ column dimension must stay in sync.** The embedding model, `EMBED_DIM` in `core/embeddings.py`, and the `vector(...)` size of `listing_embedding.embedding` must always agree. `gemini-embedding-001` is 3072-dim natively and we truncate to 768; if you change the model or dimension, it's a new Alembic migration to resize the column **plus** `make embed ARGS='--reset'` to re-embed. Drift here is an insert-time error.

## Working loop (how to make changes here)

1. Pick one task. Confirm its acceptance criteria in `docs/SPEC.md`.
2. If it changes architecture, write/append an ADR first.
3. Write or update the test/eval that defines "done."
4. Implement the smallest change that passes.
5. Run tests + lint. Read the diff yourself.
6. Commit with a clear message. Open a PR if the change is non-trivial.

## Definition of done

A change is done only when: tests/evals pass, lint is clean, types check, the diff has been read, and any new behavior is reflected in the relevant doc (SPEC/ADR/system_prompts/README). Partial work stays on its branch, never merged green-washed.

## Things an agent must NOT do

- Add a paid service or exceed the €0 budget.
- Put the LLM in the ranking/scoring path.
- Return unvalidated model output to the user.
- Commit secrets or real personal data.
- Generate apartment images with a paid model (use Pexels/Unsplash).
- Mark a task complete with failing tests.
