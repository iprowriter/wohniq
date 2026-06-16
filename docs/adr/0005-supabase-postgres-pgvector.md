# ADR-0005 — Supabase Postgres + pgvector for storage and search

**Status:** Accepted · **Date:** 2026-06-15

## Context

WohnIQ needs relational storage (listings, photos, caches, risk assessments), vector similarity for semantic search (SPEC F2), file storage for the small amount of data we host, and optionally auth for saved searches. The €0 budget constraint (ADR-0003) rules out paid managed databases. We host the backend on Railway, but want the database decoupled from it.

## Decision

Use **Supabase free tier** as the data layer: managed **Postgres** for relational data, the **pgvector** extension for embedding similarity search (semantic retrieval over Gemini embeddings), **Supabase Storage** for any hosted assets, and **Supabase Auth** if/when we add accounts. Schema changes are managed via versioned SQL migrations checked into `backend/data/`.

## Alternatives considered

- **Railway Postgres:** rejected as default — would consume the existing Railway budget/resources and couples DB lifecycle to the app; Supabase free keeps them separate and adds pgvector + storage + auth out of the box.
- **SQLite + a vector lib (FAISS/Chroma):** rejected — fine locally but awkward to deploy and demo; Postgres+pgvector is the more credible "production" story.
- **Dedicated vector DB (Pinecone/Weaviate):** rejected — extra service, potential cost, unnecessary at 100-listing scale.

## Consequences

- **+** One free service covers relational + vector + storage + auth.
- **+** pgvector keeps semantic search inside Postgres — simpler, one query path, credible architecture.
- **+** Migrations make the DB reproducible and seedable (supports demo + evals).
- **−** Free-tier projects **pause after ~1 week of inactivity** — a real problem for a portfolio link opened weeks later. Mitigation: a free GitHub Actions cron pings the project to keep it warm, and the README notes cold-start behavior.
- **−** Free-tier size limits (DB/storage) are ample for synthetic scale but cap growth (acceptable; this is not a startup).
