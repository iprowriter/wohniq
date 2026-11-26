# ADR-0016 — Berlin open data in Supabase (PostGIS), with offline build files

**Status:** Accepted · **Date:** 2026-11-24

## Context

The "Berlin Ink" redesign (`docs/design/berlin-ink/`, from `../berlinvisualized`) adds three
features that need Berlin-wide open data, not just the 100 synthetic listings:

- **Rent check** — the Berliner Mietspiegel 2026 table (189 rows), its feature checklist
  (Orientierungshilfe), and the location class (Wohnlage) of all 400,505 residential
  addresses, searchable by street and house number.
- **Around this flat** — schools, Kitas, parks, playgrounds, stops, air quality, road
  accidents and recorded crime around any point, each placed among Berlin's 542 planning
  areas.
- **Right now** — the nearest stops with their transport types, for the offline fallback.

The source files are already downloaded and checksummed in Berlin Visualized
(`data/raw/`, 446 MB, `sources.json`). WohnIQ must also keep working **offline** (demo
mode, ADR-0008), where it uses no database at all.

An earlier prototype of this redesign ran the Berlin data in PGlite (Postgres compiled to
WebAssembly), which needs a Node process next to the Python backend. We don't want Node on
Railway, or a second database engine.

## Decision

1. **One build command, raw files never committed.** `make berlin-data` reads the raw files
   from a Berlin Visualized checkout (`BERLIN_RAW_DIR`, default
   `../berlinvisualized/data/raw`), verifies each SHA-256 against
   `backend/data/berlin/sources.py`, and writes compact derived files to
   `backend/data/berlin/build/` (gitignored). Only the build code, the source registry and
   the checksums are committed. Berlin Visualized's code is not used — only its data.
2. **Live mode: Supabase with PostGIS.** `make berlin-load` loads the build files into
   WohnIQ's own Supabase database (`berlin_*` tables, Alembic migration 0003). PostGIS is
   installed into the `extensions` schema (Supabase's convention), so its `spatial_ref_sys`
   table stays out of `public`; `env.py` also filters it, so autogenerate can never propose
   dropping it. Distances use `geography` (metres on the ellipsoid).
3. **Offline mode: the same build files, read directly.** Demo mode loads the build files
   into memory (NumPy arrays, a sorted address index) instead of querying Postgres.
4. **One interface, two implementations, one parity test.** Feature code talks to a
   `BerlinData` repository (`backend/berlin/`). A test runs the same questions against the
   Postgres and the in-memory implementation and requires the same answers (park distances
   within 25 m, since the offline side measures to densified outlines).
5. **Planning-area comparisons are precomputed at build time.** For each of the 542 planning
   areas the build measures every "Around this flat" figure at a sample of its residential
   addresses and stores the median. "Closer than 73% of Berlin's 542 planning areas" is
   then a lookup, identical in both modes.
6. **Transport types come from the VBB timetable** already in the project
   (`data/vbb/network_*`, `make demo-stops`), matched to the BVG stop list by station id.
   Stops without a timetable match are labelled "Stop".
7. **Describe, don't judge** (design rule): population, election and social-monitoring
   data are not loaded. Crime is shown at district-region level only, using the same parser
   and figures as Berlin Neighbourhoods (`data/neighborhoods/parse.py`).

## Alternatives considered

- **PGlite in Node next to Python.** Works offline with one engine, but adds Node to the
  Railway image and a sidecar process to supervise. Rejected by the project owner.
- **SQLite for both modes.** Pure Python, but a second SQL dialect and no PostGIS; live mode
  would no longer be the Supabase story of ADR-0005.
- **Commit the derived files.** Simplest offline setup, but about 60 MB of generated data
  in git, regenerated on every change.
- **Offline mode without the new features.** Breaks the design's "offline first" rule.

## Consequences

- \+ No new runtime service or language; Railway stays Python-only. €0 (Supabase free tier).
- \+ Every figure traces back to a checksummed official file.
- − Two implementations of each spatial query; the parity test keeps them honest.
- − A fresh checkout needs the Berlin Visualized raw files and one `make berlin-data`
  before the new features work (offline or live); the app says so when they're missing.
- − Database size: about 100–150 MB of the free tier's 500 MB.
