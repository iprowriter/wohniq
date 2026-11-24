# ADR-0019 — Offline base map (PMTiles) and the Berlin Ink design foundations

**Status:** Accepted · **Date:** 2026-11-24 · Amends ADR-0008 (offline map fallback) and ADR-0015

## Context

Every map (homepage, listing page, Lifestyle, Neighbourhoods) loaded raster tiles from
`tile.openstreetmap.org`; offline, they fell back to area outlines on a blank background. The
Berlin Ink redesign (`docs/design/berlin-ink/`) asks for "offline first: everything except
live departures works without a network", and Berlin Visualized already ships a vector base
map of Berlin: `data/map/berlin.pmtiles` (Protomaps basemap v4 from OpenStreetMap, zoom 0–15,
98 MB, one file read with HTTP range requests). The redesign also needs shared colours, type
and components before any page can be rebuilt.

## Decision

1. **One local map file.** `make berlin-data` copies `berlin.pmtiles` (SHA-256 checked) into
   the build; the API serves it at `/tiles/berlin.pmtiles` (Starlette static files, range
   requests, range headers exposed to the frontend). A deployment without the build points
   `NEXT_PUBLIC_MAP_TILES_URL` at another copy (e.g. a public Supabase Storage object).
2. **Drawn in the browser with `protomaps-leaflet`** (new dependency, pinned 5.1.0: renders
   PMTiles vector tiles on Leaflet canvases, so no tile server and no style server), styled by
   our own complete "flavor" in Berlin Ink colours (`lib/map/basemap.ts`). All four maps use
   one `<OfflineBasemap>` component; their existing fallback (outlines) stays for a server
   without the file, detected by a 7-byte range request for the PMTiles header.
3. **A test fails if an online tile server or Leaflet `TileLayer` comes back**
   (`tests/basemap.test.ts`).
4. **Design tokens** from `tokens.css` become CSS variables (`app/globals.css`) and Tailwind
   colours (`ink`, `ground`, `accent`, `ok`, `warn`, `map.*`, `bvg.*`, …). One deviation:
   `text-faint` is darkened from #9AA3B2 to #6B7385, because the original fails 4.5:1 on white.
5. **Geist is bundled** (`geist` package, pinned 1.9.2, self-hosted through `next/font`), so the
   type works offline with no Google Fonts request.
6. **Shared building blocks** (`components/ui/`): chips, buttons (44 px), verdict cards,
   comparison bar, source label, rent scale (layout in a tested pure module), and BVG-style
   transport icons drawn as SVG (S, U, tram, bus, ferry, regional, and the "H" sign for an
   unknown stop type), each with an accessible name. `/styleguide` shows them all.
7. **New header and footer**: ink header with the four sections (Search, Lifestyle match,
   Neighbourhoods, Rent check), a status badge from `/api/v1/status` ("Demo data · offline/
   online", "Live data"), a phone menu, a skip link, and one `<main>` landmark per page.

## Alternatives considered

- **MapLibre GL JS** with a style JSON: a full WebGL stack and a rewrite of every Leaflet map
  (markers, GeoJSON layers, tests). Leaflet + protomaps-leaflet keeps the existing maps.
- **Pre-rendered raster tiles**: several GB for z0–15 and a second build step.
- **Keep online tiles with an offline fallback**: breaks the design's offline rule.

## Consequences

- \+ Every map shows streets, parks and water with no network; the design colours apply.
- \+ The app makes no third-party request for maps or fonts.
- − 98 MB served by the backend (or storage); the browser fetches only the byte ranges it needs.
- − Labels render with the system's Geist/Inter fallback in canvas; no glyph server.
