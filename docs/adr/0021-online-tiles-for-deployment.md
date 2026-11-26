# ADR-0021 — Online Protomaps tiles for the deployed site

**Status:** Accepted · **Date:** 2026-11-26 · Amends ADR-0019 (offline base map)

## Context

ADR-0019 draws every map from one local PMTiles file of Berlin (98 MB) served by the API.
The Railway image leaves the Berlin build out (live mode reads Supabase), so the deployed site
needs the map from somewhere else. The full file is over the Supabase free plan's 50 MB upload
limit; a zoom-14 copy (`make map-web`, 38 MB) fits but still has to be uploaded and kept, and
it only covers Berlin, so zooming out shows a blank edge.

## Decision

1. **`NEXT_PUBLIC_MAP_TILES_URL` accepts a `{z}/{x}/{y}` tile address** in the same Protomaps
   basemap v4 format, besides a PMTiles file. For the deployed site that is the Protomaps
   API (`https://api.protomaps.com/tiles/v4/{z}/{x}/{y}.mvt?key=…`): the same Berlin Ink
   styling (`protomaps-leaflet` with our flavor), all of Germany and beyond, nothing to host.
2. **Offline stays the default.** Without the variable, maps draw the local file, and demo
   mode never contacts anything (`e2e/offline.spec.ts`). No tile server is hard-coded.
3. **Availability check.** A tile address is probed with the single world tile (0/0/0); a PMTiles
   file with its header, whose byte 101 also gives the max zoom, so a smaller copy works. If the
   probe fails (offline, bad key), maps fall back to area outlines, as before.
4. **Credits** say "offline map" only for a file; online they read "© OpenStreetMap
   contributors · Protomaps", as the Protomaps terms require.

## Consequences

- One new outside service for the deployed site, free for non-commercial use (a portfolio
  project) with a free key; still €0 (ADR-0003). The key is public in the browser like every
  map key; restrict it to the site's domain in the Protomaps dashboard. It lives in Vercel's
  variables, never in git.
- The deployed maps depend on the Protomaps API being up; offline and demo mode don't.
- The `make map-web` copy remains an alternative (any host with range requests and CORS).
- Tests: `tests/basemap.test.ts` (template detection, world-tile probe, bad key and offline
  fallback, credits, header max zoom); checked end-to-end with `pmtiles serve` as a stand-in
  for the API.
