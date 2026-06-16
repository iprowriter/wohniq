# Convenience commands. Run `make help` to list them.
# Backend uses uv: `uv sync` builds the venv + installs deps from uv.lock;
# `uv run` executes inside that venv (no manual activation needed).
# Mirrors the commands documented in AGENTS.md.

.PHONY: help install migrate migrate-status dev test lint format frontend-dev

help:
	@echo "install        uv sync — create .venv + install deps (incl. dev group)"
	@echo "migrate        Apply pending SQL migrations"
	@echo "migrate-status List applied vs pending migrations"
	@echo "dev            Run the FastAPI backend with reload"
	@echo "test           Run pytest (unit tests + AI evals)"
	@echo "lint           Ruff check + Black --check"
	@echo "format         Auto-format with Black + Ruff --fix"
	@echo "frontend-dev   Run the Next.js dev server"

install:
	cd backend && uv sync

migrate:
	cd backend && uv run alembic upgrade head

migrate-status:
	cd backend && uv run alembic current && uv run alembic history

dev:
	cd backend && uv run uvicorn app.main:app --reload

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run black --check .

format:
	cd backend && uv run black . && uv run ruff check --fix .

frontend-dev:
	cd frontend && npm run dev
