# Berlin Neighborhoods — user flow (review set)

Captured in headless Chromium against the offline demo backend (`make demo`) and the production build. The sandbox has no internet, so the map shows the offline background instead of OSM tiles. Online, the OpenStreetMap tiles appear under the outlines.

| # | Step |
|---|---|
| 01 | Homepage: "Berlin Neighborhoods" in the header menu |
| 02 | After clicking it: `/neighborhoods`, overall ranking, list left + map right |
| 03 | Scrolled: ranked list (#, score, top/bottom-20% badge) next to the full shaded map with top-10 markers |
| 04 | Hovering a row (Lankwitz) outlines the area on the map |
| 05 | Clicking an area on the map (Helmholtzplatz) → the sidebar scrolls to it and opens its detail; the map zooms in |
| 06 | Category switched to Safety → re-ranked list and recoloured map ("Lowest crime first") |
| 07 | "Highest crime first" → the areas with the most recorded crime, orange markers |
| 08 | Affluence, Grunewald selected: summary, strengths/watch-outs, metrics vs. Berlin |
| 09 | Affluence detail: status index, land-value index, typical land value, income shown Berlin-wide only |
| 10 | "About this data": category caveat, method per metric, sources |
| 11 | Education category (district school figures + nearby schools/Kitas) |
| 12 | District filter "Mitte": 10 of 143 shown, ranks stay Berlin-wide, other areas greyed out |
| 13 | "What matters to you?": weights changed, not yet applied |
| 14 | After "Update ranking": weighted overall ranking, new order and map |
| 15 | Mobile: menu entry, map above the list |
| 16 | Mobile: Safety category, list below the map |
| 17 | Mobile: tapping an area on the map (Müggelheim) opens its detail in the list |
