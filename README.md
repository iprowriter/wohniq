# WohnIQ

**AI-assisted apartment search for Berlin.** Describe what you want in plain language — _"I work near Alexanderplatz, budget €1,500, quiet area, good transport, cafes nearby"_ — and WohnIQ parses it, searches, ranks, explains each match, and flags suspicious listings.

> **Portfolio project.** Listings are synthetic by design (see [`docs/adr/0003`](docs/adr/0003-synthetic-data-and-images.md)). The goal is to demonstrate production-grade AI engineering: reliable structured LLM output, language-vs-logic separation, a measurable scam detector, tests, evals, and a deployable system.

## Status

🚧 Early scaffolding (M1). See [`TASKS.md`](TASKS.md) for the current step.

## How this repo is organized

| File | Purpose |
|------|---------|
| [`docs/SPEC.md`](docs/SPEC.md) | **What** WohnIQ does — product spec + acceptance criteria |
| [`docs/adr/`](docs/adr/) | **Why** — architecture decision records |
| [`docs/system_prompts.md`](docs/system_prompts.md) | Versioned product LLM prompts + schemas |
| [`AGENTS.md`](AGENTS.md) | **How we work** — conventions, rules, the build loop |
| [`TASKS.md`](TASKS.md) | **What's next** — the ordered task plan |

## Architecture (one line)

`User query → LLM parser → DB + semantic search → deterministic ranking → AI explanation + scam check → results`

The LLM handles *language* (parsing, reading fuzzy text, explaining). Code handles *logic* (search, ranking, scoring). See [`ADR-0001`](docs/adr/0001-deterministic-ranking.md).

## Stack

Frontend: Next.js + Tailwind + Leaflet (Vercel). Backend: FastAPI + Pydantic (Railway, Docker). AI: Gemini Flash + embeddings. Data: Supabase Postgres + pgvector. All free / already-paid — €0 incremental.

## Quickstart

Backend uses [uv](https://docs.astral.sh/uv/). Install it once: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`). uv will fetch a matching Python automatically if you don't have 3.11+.

```bash
# Backend
cd backend
uv sync                       # creates .venv + installs deps (incl. dev tools)
cp ../.env.example ../.env    # then fill in keys
uv run alembic upgrade head   # create the schema in your Supabase DB
uv run uvicorn app.main:app --reload
uv run pytest                 # run tests + evals

# Frontend
cd frontend
npm install
npm run dev
```

From the repo root you can also use the Makefile: `make install`, `make dev`, `make test`, `make lint`.

## License / attribution

Apartment photos sourced via the Pexels API; attribution shown in-app per their terms.
