# WohnIQ Frontend

Next.js (App Router) + TypeScript. Talks to the FastAPI backend's `/search` API.

This is a **skeleton** — only the structure and dependency list exist. To make it runnable:

```bash
cd frontend
npm install          # installs the deps listed in package.json
npm run dev          # http://localhost:3000
```

The real search UI (search box, result cards with explanation + risk badge,
detail page, comparison view, Leaflet map) is built in milestone **M5 / T5.1**.

## Lifestyle Match (`/lifestyle`, `/lifestyle/results`)

Multi-step questionnaire → persona → ranked Berlin areas. Everything the UI shows comes
from `GET /api/v1/lifestyle/catalog` and the `/profile` and `/match` endpoints; answers
stay in this tab's `sessionStorage` only (ADR-0012).

- `lib/lifestyle/logic.ts` — pure questionnaire logic (steps, answers, validation, storage)
- `lib/lifestyle/results.ts` — pure results logic (weight overrides, removed areas, map colours, sources)
- `lib/lifestyle/api.ts` — API client (answers only ever in POST bodies)
- `components/lifestyle/` — UI pieces

Tests (no extra dependencies — Node's built-in runner with TypeScript type stripping):

```bash
npm test            # tests/*.test.ts
npm run typecheck
```

`tests/fixtures/lifestyle-catalog.json` is the real catalog response, exported by the
backend (`make lifestyle-fixture`); a backend test fails if it goes stale.

## Berlin Neighborhoods (`/neighborhoods`)

All 143 areas ranked by a category (or a weighted overall score): list + shaded Leaflet/OSM map, map ↔ list selection, area detail with sources, weights, search/district filter, URL state. Data from `GET /api/v1/neighborhoods/*` (see `docs/NEIGHBORHOODS.md`).

- `lib/neighborhoods/logic.ts`: pure logic (weights, URL state, filtering/ordering, rank colours, badges, source labels)
- `lib/neighborhoods/api.ts`: API client (plain GETs; no personal data)
- `components/neighborhoods/`: category tabs, list row, detail panel, weights panel, map, header link

Tests: `tests/neighborhoods.test.ts` runs against real responses in `tests/fixtures/neighborhoods-*.json` (`make neighborhoods-fixture`; a backend test fails if they go stale). `e2e/neighborhoods.spec.ts` holds the Playwright journeys.

## Homepage map ("See on the map")

Every listing from `GET /api/v1/listings/map` as a price pill; zooming out clusters into
neighbourhood, district and Berlin median rents (tiers: `lib/map/listingsMap.ts`,
decision record: `docs/adr/0015-homepage-listings-map.md`).

- `lib/map/listingsMap.ts` — pure logic: zoom tiers, medians, area clusters, pill stacking
  (tested in `tests/listings-map.test.ts`)
- `components/map/ListingsMap.tsx` — Leaflet map (pills, bubbles, card popup, tier switcher)
- `components/map/ListingMapCard.tsx` — the card shown above a clicked pill
- `components/map/ListingsMapSection.tsx` — homepage section (data loading, lazy Leaflet)

E2E journeys for this and the area-aware search: `e2e/search-and-map.spec.ts`. In a sandbox
without the Playwright browser download: `PW_CHROMIUM_PATH=/path/to/chrome npm run test:e2e`.
