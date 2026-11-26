# WohnIQ redesign: "Berlin Ink"

A target design for WohnIQ (`../wohniq`) that brings in the open Berlin data and
offline pipeline from Berlin Visualized (`../berlinvisualized`). This folder is a
reference, not code to ship: the screens are static HTML with inline styles, all
listings and numbers are sample data, and photos and maps are grey placeholders.

## What is in this folder

| Path | What it is |
|---|---|
| `screens/0-home-before-search.html` | Home before a search (1440 wide) |
| `screens/1-search-results.html` | Search results with map (1440 wide) |
| `screens/2-listing-dossier.html` | One listing, fully checked (1440 wide) |
| `screens/3-rent-check.html` | Stand-alone rent check for any address (1440 wide) |
| `screens/4-listing-mobile.html` | The listing on a phone (390 wide) |
| `screenshots/*.png` | Full-page captures of the five screens, same names |
| `tokens.css` | Every colour, font size and radius the screens use, as CSS variables |

Open the HTML files directly in a browser; they need nothing but the Geist font
from Google Fonts (they fall back to Inter or the system font offline). The main
path is linked: home search and example queries → results → "View dossier" →
listing → "Open the full rent check" → rent check, and the logo on the listing
and rent-check pages goes back to results. Links marked `href="#"` are not wired
in the mockup (Lifestyle match and Neighbourhoods are not designed yet).

## Product idea in one line

"Find your Berlin flat. Know it's fair before you call." Every listing gets three
verdicts, each explained in plain words:

1. **Fit**: how well it matches what the user typed (0–100, with reasons).
2. **Rent check**: cold rent per m² against the Berliner Mietspiegel 2026 range
   and the rent-brake limit (index mean + 10%).
3. **Scam risk**: low / elevated, with the signals that were checked.

## Screens

### 0 · Home before a search
- Dark hero: eyebrow, display headline, one-line promise, the free-text search box
  and three example queries ("Try: …").
- Right of the hero: "Every listing, checked" card showing one sample listing with
  its verdict chips, and three ticks (rent, scam signals, surroundings).
- "Not sure where to start?": three entry cards: Lifestyle match, Explore
  neighbourhoods (the 143 areas WohnIQ already has), Check a rent.
- "Explore Berlin": three listing cards plus a small offline map with price pins.
- "How WohnIQ works": 01 describe, 02 rank and check, 03 see why.
- Footer: sample-data notice, sources, "Works offline · No account needed".

### 1 · Search results
- Same header with the query filled in, and "We understood:" chips showing how
  the text was parsed (area, rooms, budget, quiet, park). Chips are editable.
- Result cards: fit badge on the photo, title, area, facts, verdict chips (fair
  rent or above index with the numbers, risk), commute chip, one sentence on why
  it ranks here, and View dossier / Compare / Save.
- Sticky map on the right: the searched area outlined, price pins, layer toggles
  (Listings, Median rent, Transit, Green).
- Toolbar: Sort, "Only fair rents", Share search.

### 2 · Listing dossier
- Photo grid, title block, three verdict cards (fit, rent check, scam risk).
- Price card (warm, cold, service charges, deposit, per m²) with Request a viewing,
  Save, Compare.
- **Rent check** panel: a horizontal scale with the index range (teal), the mean,
  the rent-brake limit (amber line) and the asked rent (accent dot), plus a
  not-legal-advice line.
- **Right now**: live departures from the nearest station, with an offline
  fallback message.
- **Commute** to a place the user chose, with a route map placeholder.
- **Around this flat**: eight measures, each with its source, a bar showing where
  the flat sits among Berlin's 542 planning areas, and a neutral sentence.
- **Why the risk is low**: the checks that passed.

### 3 · Rent check
- Form: address (with location class found), size, building age, cold rent,
  energy value, Mietspiegel feature checklist.
- Result: verdict panel, three number tiles (range, limit, you pay), a bar chart of
  mean rents by building age, a link to flats with fair rents, Print / PDF, and the
  exceptions to the rent brake.

### 4 · Listing on a phone
- Full-width photo with back and share, title, three compact verdict tiles, rent
  check scale, Right now, the first six "Around this flat" measures, and a sticky
  bottom bar with the warm rent and Request viewing.

## Where each section's data comes from

All of these datasets are already downloaded, documented and checksummed in
`../berlinvisualized/data/sources.json` (files under `data/raw/`). Ids below are the
`id` values in that file.

| Section | Dataset ids |
|---|---|
| Rent check, location class | `living.rent_index_table_2026`, `living.rent_index_mietspiegel_2026`, `living.rent_index_residential_location_2026` |
| Nearest S/U-Bahn, Right now (offline fallback) | `mobility.bvg_stations`, `snapshots.bvg_stops_raw` |
| Schools within 1 km | `living.schools` |
| Kitas within 500 m | `living.daycare_centers_2025-11` |
| Parks and playgrounds | `living.parks`, `living.playgrounds` |
| Air quality | `environment.air_quality_stations_luftdaten`, `snapshots.air_quality_index_latest` |
| Road accidents nearby | `mobility.traffic_accidents_2025_berlin` |
| Recorded crime (district region level only) | `society.crime_atlas_2016-2025` |
| Comparison areas, map outlines | `boundaries.lor_planning_areas_2021`, `boundaries.lor_district_regions_2021`, `boundaries.districts` |
| Offline base map | `berlinvisualized/data/map/berlin.pmtiles` (OpenStreetMap) |

"Right now" departures are live in the real product (BVG/VBB API) and must fall
back to station and walking time when offline. Listings themselves stay synthetic
(WohnIQ demo mode); no real listing data is included.

## Rules the redesign follows

- **Describe areas, don't judge them.** Never rank or colour an area by who lives
  there. Population, election and social-monitoring data in Berlin Visualized are
  not used for scores, chips or "Around this flat".
- **Verdicts are calm.** Two states plus neutral: teal for fine, amber for "worth
  asking", grey for neutral. No red for rent or area.
- **Every number has a source** shown next to it, and the app says when data is a
  snapshot.
- **Rent results are estimates, not legal advice**, and the rent-brake exceptions
  are always listed near the verdict.
- **Offline first.** Everything except live departures works without a network.
- **Accessible.** Real headings and landmarks, labelled inputs, everything
  clickable at least 44 px tall, text contrast at least 4.5:1, numbers in tabular
  figures, nothing conveyed by colour alone (chips always carry words).

## Sample data used across all screens

Listing "Bright 2-room flat by Weinbergspark", Mitte · Rosenthaler Vorstadt,
Choriner Str. 41: 2 rooms, 61 m², built 1908 (before 1918), €1,284 warm, €860 cold,
€424 service charges, €2,580 deposit, €14.10/m² cold. Mietspiegel range
€11.60–15.20 (mean €13.40), rent-brake limit €14.74. Fit 92, scam risk low (12/100).
These figures are invented for the mockup and only need to be consistent, not real.
