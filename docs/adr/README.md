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
| [0007](0007-direct-sdk-over-agent-framework.md) | Direct Gemini SDK over LangChain/LangGraph | Accepted |
| [0008](0008-offline-commute-estimate.md) | Offline commute estimate from straight-line distance and published speeds | Accepted, amended by 0009 and 0014 |
| [0009](0009-route-based-commute-estimate.md) | Route-based commute estimate over the VBB weekday-peak network | Accepted |
| [0010](0010-lifestyle-match-data-model.md) | Lifestyle Match: official-data region profiles with provenance | Accepted |
| [0011](0011-lifestyle-match-scoring.md) | Lifestyle Match: answers → weights → deterministic, explained ranking | Accepted |
| [0012](0012-privacy-by-design.md) | Privacy by design: lifestyle answers are never stored or logged | Accepted |
| [0013](0013-berlin-neighborhoods.md) | Berlin Neighborhoods: ranked area profiles from official data | Accepted (amends 0010's data-ethics section for this feature) |
| [0014](0014-area-aware-search.md) | Area-aware search: Berlin areas are a hard filter, with a labelled nearby fallback | Accepted (amends 0008 decision 6) |
| [0015](0015-homepage-listings-map.md) | Homepage listings map: zoom tiers, median clusters and price pills | Accepted |
| [0016](0016-berlin-open-data-in-supabase.md) | Berlin open data in Supabase (PostGIS), with offline build files | Accepted |
