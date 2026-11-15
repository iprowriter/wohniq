# ADR-0015 — Homepage listings map: zoom tiers, median clusters and price pills

**Status:** Accepted · **Date:** 2026-11-14

## Context

The homepage gets a "See on the map" section under "Explore Berlin": every listing on the
existing OpenStreetMap/Leaflet map as a purple price pill; a click opens a card (photo, warm
rent, location, rooms, m²). Zoomed out, listings must cluster into the **median rent** of a
neighbourhood or district, and — once other cities are on screen — of **Berlin as a whole**.
We had to decide where each level starts and how to keep ~100 pills legible.

## Decision

1. **Four semantic tiers by zoom** (`frontend/lib/map/listingsMap.ts`, pure + unit-tested).
   At Berlin's latitude one pixel is ≈ 93 m at z10, 47 m at z11, 23 m at z12, 12 m at z13:

   | Zoom | Shows | Why this range |
   |---|---|---|
   | ≤ 10 | One **Berlin median** bubble ("Berlin median rent") | A desktop map spans ≥ ~100 km: Potsdam, Oranienburg etc. are visible, and district bubbles would overlap (checked in screenshots) |
   | 11 | **District (Bezirk) medians**, at each Bezirk's geographic centre | Bezirk centres are ≥ ~100 px apart; a unit test checks no two bubbles overlap |
   | 12 | **Neighbourhood (Kiez) medians** | Kiez centres are ≥ ~70 px apart |
   | ≥ 13 | **Individual price pills** (opens here, ~60 listings in view) | Pills that would overlap are stacked into a "N flats" pill up to z15; from z16 every listing has its own pill |

   Each zoom step moves exactly one tier. Clicking a median bubble opens the next tier
   centred on it (Berlin → districts → neighbourhoods → listings; never skipping one);
   clicking a stack zooms 1–2 levels, just enough to separate it. A tier switcher
   (Berlin · Districts · Neighbourhoods · Listings) and a status line ("Median warm rent by
   district · 100 listings") make the current level explicit.
2. **Semantic clusters, not only geometric ones.** Aggregates are grouped by the listing's
   Bezirk/Kiez so the bubble can be *named* and its median is meaningful ("Kreuzberg · 13 ·
   €1.125 median"). Geometric stacking is used only at listing level, against the real
   rendered pill size, with stacks anchored so that no two markers overlap (tested).
3. **Warm rent everywhere**, formatted like the rest of the UI (€1.068), medians of warm
   rent. The selected listing always keeps its own pill (never hidden in a stack).
4. **One lightweight endpoint**, `GET /api/v1/listings/map`: id, coordinates, warm rent,
   Kiez/district, rooms, m², cover photo, risk band. Medians are computed client-side from
   the same points, so the numbers on the map always agree with the pills.
5. **State feedback:** the clicked pill turns white with a purple ring (selected), pills
   already opened turn lavender (visited). Pills are keyboard-focusable buttons; Enter/Space
   opens the card, Escape closes it. The wheel zooms only after the map is clicked, so the
   homepage never hijacks page scrolling.
6. **Offline:** same rule as the listing map — if no tile loads within 4 s, a clean
   background with Berlin's area outlines is shown and a caption explains why.

## Alternatives considered

- **Leaflet.markercluster / Supercluster.** Purely geometric clusters can't be named after a
  neighbourhood or show "the Berlin median", and would add a dependency for ~100 points.
- **District bubbles at the listings' centroid.** Rejected after screenshots: listings
  concentrate in the inner city, so all district bubbles piled up in the centre.
- **Opening at z14.** Only ~15 listings in view; z13 shows ~60 with few stacks.

## Consequences

- \+ Every level is legible and named; the medians are explainable and tested.
- − The district and neighbourhood tiers are one zoom level each (a deliberate trade-off for
  legibility); the tier switcher jumps straight to any level.
- − District label points are a small hard-coded table (same figures as the backend
  gazetteer); an unknown district falls back to its listings' centroid.
