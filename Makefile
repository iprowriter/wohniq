# Convenience commands. Run `make help` to list them.
# Backend uses uv: `uv sync` builds the venv + installs deps from uv.lock;
# `uv run` executes inside that venv (no manual activation needed).
# Mirrors the commands documented in AGENTS.md.

.PHONY: help install migrate migrate-status seed dev demo demo-photos demo-stops lifestyle-data lifestyle-fixture neighborhoods-data neighborhoods-fixture berlin-data berlin-load eval-neighborhoods test test-all lint frontend-test format frontend-dev

help:
	@echo "install        uv sync — create .venv + install deps (incl. dev group)"
	@echo "migrate        Apply pending SQL migrations"
	@echo "migrate-status List applied vs pending migrations"
	@echo "seed           Seed synthetic listings (use ARGS='--reset')"
	@echo "seed-images    Seed listing photos from Pexels (use ARGS='--reset')"
	@echo "seed-extra     Add the 40 extra listings (ADR-0018) to a seeded database"
	@echo "embed          Backfill listing embeddings into pgvector"
	@echo "score          Score all listings into risk_assessment (ARGS='--no-llm')"
	@echo "eval-parser    Run the parser eval (20 canonical queries; hits Gemini)"
	@echo "eval-ranking   Run the ranking sanity eval (offline)"
	@echo "eval-scam      Run the scam-detection eval (DB; ARGS='--no-llm' to skip LLM)"
	@echo "eval-lifestyle Run the Lifestyle Match eval (offline; scenarios + properties)"
	@echo "eval-neighborhoods Run the Berlin Neighbourhoods eval (offline; ground truth + properties)"
	@echo "eval-commute   Offline commute estimates vs. live VBB journeys (online; ARGS='--offline')"
	@echo "neighboorhood  Populate neighboorhood_cache table"
	@echo "dev            Run the FastAPI backend with reload"
	@echo "demo           Run the backend in offline demo mode (no DB/APIs; WOHNIQ_DEMO=1)"
	@echo "demo-photos    Download local copies of demo photos (run once while online)"
	@echo "demo-stops     Download VBB stops + peak network for offline commute estimates (once, online)"
	@echo "lifestyle-data Rebuild Lifestyle Match region profiles from the official files in data/lifestyle/raw/"
	@echo "neighborhoods-data Rebuild the Berlin Neighbourhoods bundle from data/neighborhoods/raw/"
	@echo "berlin-data    Build rent index, addresses, stops, schools… from Berlin Visualized raw files (BERLIN_RAW_DIR)"
	@echo "berlin-load    Load the berlin-data build into Supabase (needs make migrate)"
	@echo "neighborhoods-fixture Refresh the frontend's neighbourhoods contract fixture from the API"
	@echo "test           Run pytest (unit tests + AI evals)"
	@echo "test-all       Run pytest including slow tests (e.g. Lifestyle data rebuild)"
	@echo "lint           Ruff check + Black --check"
	@echo "format         Auto-format with Black + Ruff --fix"
	@echo "frontend-dev   Run the Next.js dev server"
	@echo "frontend-test  Run the frontend logic tests (node --test, no extra deps)"
	@echo "lifestyle-fixture Refresh the frontend's catalog contract fixture from the API"
	@echo "frontend-build   Run the Next.js build files "

install:
	cd backend && uv sync

migrate:
	cd backend && uv run alembic upgrade head

migrate-status:
	cd backend && uv run alembic current && uv run alembic history

seed:
	cd backend && uv run python -m data.seed_listings $(ARGS)

seed-extra:
	cd backend && uv run python -m data.seed_extra_listings

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

eval-lifestyle:
	cd backend && uv run python -m evals.lifestyle_eval

eval-neighborhoods:
	cd backend && uv run python -m evals.neighborhoods_eval

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

lifestyle-data:
	cd backend && uv run python -m data.lifestyle.build_profiles $(ARGS)

lifestyle-fixture:
	cd backend && uv run python -m data.lifestyle.export_catalog

neighborhoods-data:
	cd backend && uv run python -m data.neighborhoods.build_index $(ARGS)

berlin-data:
	cd backend && uv run python -m data.berlin.build $(ARGS)

berlin-load:
	cd backend && uv run python -m data.berlin.load $(ARGS)

neighborhoods-fixture:
	cd backend && uv run python -m data.neighborhoods.export_fixture

frontend-test:
	cd frontend && npm test

test:
	cd backend && uv run pytest

test-all:
	cd backend && uv run pytest -m ""

lint:
	cd backend && uv run ruff check . && uv run black --check .

format:
	cd backend && uv run black . && uv run ruff check --fix .

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
