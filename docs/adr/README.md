# Architecture Decision Records

ADRs capture *why* a significant decision was made — the context, the choice, the alternatives, and the consequences. They are append-only history: when a decision changes, write a new ADR that supersedes the old one rather than editing it.

Format: lightweight [MADR](https://adr.github.io/madr/)-style.

| # | Title | Status |
|---|-------|--------|
| [0001](0001-deterministic-ranking.md) | Ranking is deterministic; LLM never scores or orders | Accepted |
| [0002](0002-hybrid-scam-detection.md) | Scam detection is a hybrid rules + pHash + LLM engine | Accepted |
| [0003](0003-synthetic-data-and-images.md) | Synthetic listings with hotlinked stock photos | Accepted |
| [0004](0004-gemini-structured-output.md) | Gemini Flash with validated structured output | Accepted |
| [0005](0005-supabase-postgres-pgvector.md) | Supabase Postgres + pgvector for storage and search | Accepted |
| [0006](0006-orm-sqlalchemy-alembic.md) | SQLAlchemy 2.0 + Alembic; raw SQL for vector/ranking | Accepted |
