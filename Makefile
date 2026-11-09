# Convenience commands. Run `make help` to list them.
# Backend uses uv: `uv sync` builds the venv + installs deps from uv.lock;
# `uv run` executes inside that venv (no manual activation needed).
# Mirrors the commands documented in AGENTS.md.

.PHONY: help install migrate migrate-status seed dev demo demo-photos demo-stops test lint format frontend-dev

help:
	@echo "install        uv sync — create .venv + install deps (incl. dev group)"
	@echo "migrate        Apply pending SQL migrations"
	@echo "migrate-status List applied vs pending migrations"
	@echo "seed           Seed synthetic listings (use ARGS='--reset')"
	@echo "seed-images    Seed listing photos from Pexels (use ARGS='--reset')"
	@echo "embed          Backfill listing embeddings into pgvector"
	@echo "score          Score all listings into risk_assessment (ARGS='--no-llm')"
	@echo "eval-parser    Run the parser eval (20 canonical queries; hits Gemini)"
	@echo "eval-ranking   Run the ranking sanity eval (offline)"
	@echo "eval-scam      Run the scam-detection eval (DB; ARGS='--no-llm' to skip LLM)"
	@echo "eval-commute   Offline commute estimates vs. live VBB journeys (online; ARGS='--offline')"
	@echo "neighboorhood  Populate neighboorhood_cache table"
	@echo "dev            Run the FastAPI backend with reload"
	@echo "demo           Run the backend in offline demo mode (no DB/APIs; WOHNIQ_DEMO=1)"
	@echo "demo-photos    Download local copies of demo photos (run once while online)"
	@echo "demo-stops     Download VBB stops + peak network for offline commute estimates (once, online)"
	@echo "test           Run pytest (unit tests + AI evals)"
	@echo "lint           Ruff check + Black --check"
	@echo "format         Auto-format with Black + Ruff --fix"
	@echo "frontend-dev   Run the Next.js dev server"
	@echo "frontend-build   Run the Next.js build files "

install:
	cd backend && uv sync

migrate:
	cd backend && uv run alembic upgrade head

migrate-status:
	cd backend && uv run alembic current && uv run alembic history

seed:
	cd backend && uv run python -m data.seed_listings $(ARGS)

seed-images:
	cd backend && uv run python -m data.seed_images $(ARGS)

embed:
	cd backend && uv run python -m data.embed_listings $(ARGS)

score:
	cd backend && uv run python -m scam.score $(ARGS)

eval-parser:
	cd backend && uv run python -m evals.parser_eval $(ARGS)

eval-ranking:
	cd backend && uv run python -m evals.ranking_eval

eval-scam:
	cd backend && uv run python -m evals.scam_eval $(ARGS)

eval-commute:
	cd backend && uv run python -m evals.commute_eval $(ARGS)

neighboorhood:
	cd backend && .venv/bin/python data/enrich_neighborhoods.py

dev:
	cd backend && uv run uvicorn app.main:app --reload

demo:
	cd backend && WOHNIQ_DEMO=1 uv run uvicorn app.main:app --reload

demo-photos:
	cd backend && uv run python -m data.fetch_demo_photos

demo-stops:
	cd backend && uv run python -m data.fetch_vbb_stops $(ARGS)

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run black --check .

format:
	cd backend && uv run black . && uv run ruff check --fix .

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
