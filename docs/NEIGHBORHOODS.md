# Berlin Neighborhoods

> All 143 Berlin neighborhoods on one map, ranked by whatever matters to you: crime, road safety, affluence, education, healthcare, amenities, parks, public transport, quiet & clean air, parking or rent. Every number shows its source.

Open it from the header menu (**Berlin Neighborhoods**) or at `/neighborhoods`.

Decision record: [ADR-0013](adr/0013-berlin-neighborhoods.md).

| Overall ranking: list left, OSM map right | Click an area on the map → the sidebar selects and explains it |
|---|---|
| ![Overall](screenshots/neighborhoods/1_overall_list_and_map.png) | ![Map click](screenshots/neighborhoods/2_map_click_selects_in_sidebar.png) |

| Safety: lowest crime first | Safety: highest crime first |
|---|---|
| ![Safety](screenshots/neighborhoods/3_safety_lowest_crime_first.png) | ![Highest crime](screenshots/neighborhoods/4_safety_highest_crime_first.png) |

| Area detail with sources (shared link) | "What matters to you?" weights | Mobile |
|---|---|---|
| ![Detail](screenshots/neighborhoods/5_education_detail_shared_link.png) | ![Weights](screenshots/neighborhoods/6_weights_panel.png) | ![Mobile](screenshots/neighborhoods/7_mobile_transit.png) |

| Affluence: land-value index, context land value, and income (not published per neighborhood; Berlin-wide figure shown) |
|---|
| ![Affluence](screenshots/neighborhoods/8_affluence_land_values.png) |

---

## 1. What the user can do

- **Browse every area, ranked.** The list on the left is ranked (#1–#143), with a score from 0 to 100 and a badge for Berlin's top or bottom 20%. The map on the right colours all 143 outlines by rank in five bands, from indigo (best) to orange (worst), and numbers the first ten rows of the list.
- **Switch category** with the sticky bar: ⭐ Overall, 🛡️ Safety, 🚦 Road safety, 💶 Affluence, 🎓 Education, 🏥 Healthcare, ☕ Amenities, 🌳 Parks & nature, 🚇 Public transport, 🍃 Quiet & clean air, 🅿️ Parking, 🏷️ Affordability. The list re-ranks, the map recolours, and each row shows the category's key figure (e.g. "Neighbourhood offences: 1,236 per 100,000 residents").
- **Best or worst first.** The toggle uses the category's own words: "Lowest crime first" / "Highest crime first".
- **Map ↔ list.**
  - Clicking an area on the map selects it in the sidebar: the row scrolls into view and expands. If a filter was hiding the area, the filter is cleared.
  - Hovering a row outlines the area on the map; selecting a row zooms the map to it.
  - Tapping the row again collapses it.
- **Area detail.**
  - A one-line summary ("#29 of 143 overall. Strongest: Amenities (#1); weakest: Parking (#143)").
  - Strengths and watch-outs, each quoting its figure, the Berlin figure, its rank and its source.
  - Every metric of the current category, compared with Berlin ("better than Berlin (3,198)"); district-level figures are labelled.
  - The area's rank in every category; tap one to re-rank Berlin by it.
  - "About this data": the category caveat, each metric's method, and the full source list.
- **Weights for the overall score.** Under "What matters to you?", each category can be set to Ignore / Some / Important / Top priority. Click **Update ranking** to apply.
- **Search and district filter.** Search is accent-insensitive ("muggel" finds Müggelheim). Ranks stay Berlin-wide when filtering.
- **Shareable views.** The category, the selected area and custom weights live in the URL (`/neighborhoods?category=safety&area=036013`).

## 2. Categories, metrics and sources

| Category | Metrics (weight in category) | Sources | Top 3 | Bottom 3 |
|---|---|---|---|---|
| 🛡️ **Safety** (default weight 2) | Neighbourhood offences (3); Assaults (2); Robbery (1); Home burglary (1); All reported offences (1); Bike theft (0.5); Car theft & break-ins (0.5) | Polizei Berlin, Kriminalitätsatlas | Müggelheim, Schmöckwitz, Heiligensee/Konradshöhe | Lietzenburger Straße, Schöneberg Nordwest, Südliche Luisenstadt |
| 🚦 **Road safety** (default weight 1) | Injury accidents (2); Killed or seriously injured (2); Involving pedestrians or cyclists (1) | Unfallatlas 2025 | Müggelheim, Heiligensee/Konradshöhe, Bohnsdorf | Nördliche Luisenstadt, Südliche Friedrichstadt, Tempelhofer Vorstadt |
| 💶 **Affluence** (default weight 1) | Social-status index (2); Land-value index (2); Typical land value (0) — *context*; Income per taxpayer (2) — *pending* — *district* | Gutachterausschuss, Bodenrichtwerte 2026; SenSBW, MSS 2023 | Zehlendorf Südwest, Brunnenstraße Süd, Zehlendorf Nord | Marzahn Nord, Hellersdorf Nord, Märkisches Viertel Nord |
| 🎓 **Education** (default weight 1) | School leavers with Abitur (2) — *district*; Leavers without a qualification (1) — *district*; Gymnasium recommendations (1) — *district*; Schools within 1 km (1); Kitas within 500 m (1) | OpenStreetMap (2026-11-12); SenBJF, Blickpunkt Schule 2025/26 | Volkspark Wilmersdorf, Helmholtzplatz, Schloßstraße | Gatow/Kladow, Rudow, Brunsbütteler Damm |
| 🏥 **Healthcare** (default weight 1) | Nearest hospital (2); Doctors within 1 km (2); Pharmacies within 500 m (1) | OpenStreetMap (2026-11-12) | Volkspark Wilmersdorf, Schöneberg Nordwest, Lietzenburger Straße | Schmöckwitz, Müggelheim, Malchow |
| ☕ **Amenities** (default weight 1) | Cafés & restaurants within 500 m (2); Everyday shops within 500 m (2); Culture within 1.5 km (1); Sport within 1 km (1); Bars & clubs within 1 km (0) — *context* | OpenStreetMap (2026-11-08) | Helmholtzplatz, Prenzlauer Berg Südwest, Reuterstraße | Schmöckwitz, Müggelheim, Rahnsdorf |
| 🌳 **Parks & nature** (default weight 1) | Green-space supply (2); Nearest park (≥ 1 ha) (2); Nearest water or forest (1); Playgrounds within 500 m (1) | OpenStreetMap (2026-11-08); OpenStreetMap (2026-11-12); Umweltgerechtigkeitsatlas 2023/24 | Neu-Hohenschönhausen Nord, Rollbergesiedlung, Alt-Treptow | Lietzenburger Straße, Friedenau West, Schöneberg Nordwest |
| 🚇 **Public transport** (default weight 1) | Nearest S-/U-Bahn or tram (2); Stops within 500 m (1); To Alexanderplatz (1) | OpenStreetMap (2026-11-12); VBB timetable | Regierungsviertel, Brunnenstraße Süd, Alexanderplatz | Gatow/Kladow, Müggelheim, Hakenfelde |
| 🍃 **Quiet & clean air** (default weight 1) | Traffic noise (2); Air pollution (2); Summer heat (1) | Umweltgerechtigkeitsatlas 2023/24 | Gatow/Kladow, Köpenick Süd, Malchow | Regierungsviertel, Tempelhof Südost, Alexanderplatz |
| 🅿️ **Parking** (default weight 1) | Homes in paid-parking streets (1); Car parks within 300 m (1); Population density (1) | LOR 2021 / register 2024; OpenStreetMap (2026-11-12) | Marzahn Süd, Allende-Viertel, Marzahn Mitte | Helmholtzplatz, Brunnenstraße Süd, Prenzlauer Berg Süd |
| 🏷️ **Affordability** (default weight 1) | Median asking rent (1) — *district* | IBB Tabellenband 2025 | Biesdorf, Hellersdorf Nord, Hellersdorf Ost | Wedding Zentrum, Tiergarten Süd, Regierungsviertel |

Nightlife (Amenities) and the typical land value in EUR/m² (Affluence) are shown for context but not scored. Nightlife because whether it's a plus depends on the person; land value in EUR/m² because it mostly reflects how densely land may be built on.

**How the land-value index works.** Each home sample point takes the Bodenrichtwert (1 Jan 2026) of the residential zone it lies in. It is compared only with Berlin's zones of the same kind: land for houses (GFZ ≤ 0.7) with houses, land for blocks of flats with flats. The Gutachterausschuss calls converting values between these sub-markets "fachlich unzulässig". The area's index is the mean percentile of its homes (0–100). So Grunewald's villa land (€2,700/m² median) scores 94, above many inner-city blocks priced at €5,000/m², because among *houses* it is Berlin's priciest land.

Ties share a rank (for example, areas whose planning areas are all in the top MSS class, or the areas of one district for district-level metrics).

## 3. How scores work

All of this is deterministic code: no LLM, and the same request always gives the same output.

1. **Metric score (0–100)** = the share of Berlin's 143 areas this area does better on (ties count half), read against the sorted distribution fixed in the bundle at build time. 100 = best in Berlin, 50 = middle.
2. **Category score** = weighted mean of its metric scores.
3. **Overall score** = weighted mean of the categories. Default weights: Safety 2, everything else 1. Users can set each from 0 to 3.
4. **Rank** = position by score (rounded to 0.1); equal scores share a rank. Ranks are Berlin-wide.
5. **Tiers**: the top 20% (ranks 1–29) get the category's best label, the bottom 20% (ranks 115–143) its worst label. The map uses five rank bands.

Why percentiles: they are robust to outliers (Tiergarten Süd's crime rate doesn't compress everyone else) and put all 40 metrics on the same footing, so category and overall weights mean what they say.

## 4. Data: what we have, what's still needed

Built by `make neighborhoods-data` from the files listed in [`backend/data/neighborhoods/raw/README.md`](../backend/data/neighborhoods/raw/README.md). The SHA-256 of every input is recorded in the bundle, and a rebuild reproduces it byte for byte.

| Asked for | Status |
|---|---|
| Crime rate | ✅ 7 offence rates per area, Kriminalitätsatlas 2023–2025 |
| Average income | ⚠️ **Not published per neighborhood.** The Statistischer Bericht L IV 3 – j/22 (parsed, with self-checks) covers Berlin as a whole only. The page says so and shows the Berlin-wide figure, €45,161 per taxpayer (2022); the median taxpayer is in the €30,000–35,000 bracket. Income is not scored; Affluence rests on the social-status index and the land values. |
| Wealth index (median wealth) | ⚠️ Median wealth isn't published for neighborhoods anywhere in Germany. Proxy (✅): the MSS 2023 social-status index plus the **land-value index** from the Bodenrichtwerte 2026, weighted equally. |
| Hospitals, schools, cafés | ✅ OSM distance to the nearest hospital; doctors, pharmacies, schools, Kitas; cafés, shops, culture, sport |
| Parks | ✅ Senate green-space supply class, distance to a park ≥ 1 ha, water/forest, playgrounds |
| Parking spaces | ✅ paid-parking streets (from ticket machines), mapped car-park area, density. ⚠️ On-street spaces aren't counted officially. |
| Accident rates | ✅ Unfallatlas 2025: injury, severe, and pedestrian/cyclist accidents per 10 km of street |
| Education / literacy | ⚠️ Literacy isn't published below national level. Proxy: district Abitur share, leavers without a qualification, Gymnasium recommendations (✅, 2024/25), plus nearby schools and Kitas |
| Extra categories | ✅ public transport, quiet & clean air, affordability, overall weighted score |

Wording rules (ADR-0013): labels describe the measure ("Highest crime", "Lowest status"), never the residents; nothing tells users to "avoid" an area. Every category shows its caveat.

## 5. API

| Endpoint | Returns |
|---|---|
| `GET /api/v1/neighborhoods/catalog` | categories, metrics (with Berlin figures and pending ones), sources, districts |
| `GET /api/v1/neighborhoods/ranking?category=safety` | all 143 areas, ranked, with tier and headline figure |
| `GET /api/v1/neighborhoods/ranking?weights=safety:3,parking:0` | overall ranking with custom weights (422 on bad input) |
| `GET /api/v1/neighborhoods/areas/{key}` | one area: every category and metric with source and method, highlights, summary |
| `GET /api/v1/neighborhoods/regions.geojson` | simplified outlines (same file as Lifestyle Match) |

Read-only, no database, no third-party calls, so it works unchanged in offline demo mode (`make demo`). Responses are cacheable, and logs record counts only.

## 6. Evaluation & tests

| Suite | What | Result |
|---|---|---|
| `make eval-neighborhoods` (also in pytest) | 13 ground-truth cases from well-known facts + 52 properties (determinism, direction, dominance, weight monotonicity, single focus, tier sizes, grounded highlights, provenance, wording) | **65 / 65**, no known gaps |
| Backend unit + API tests | parsers (self-checks against each publication, incl. land-value zones and the income table's bracket checksum), spatial measurement incl. land values at homes, bundle validation, scoring, explanations, endpoints, fixture freshness | 88 new tests (434 total pass) |
| Build reproducibility (`make test-all`) | rebuilds from the raw files and compares byte for byte | ✅ |
| Frontend logic (`npm test`) | contract against real API responses, weights/URL state, filtering, ordering, colours, badges, source labels | 18 new tests (52 total pass) |
| Playwright (`npm run test:e2e`) | 7 journeys × desktop + mobile, incl. the Definition of Done and the Affluence detail | 14 new (24 total pass) |

**Closed data gap.** Until the land values arrived, the eval reported a known gap: Grunewald, one of Berlin's wealthiest villa districts, wasn't in the Affluence top 20%, because the MSS index measures disadvantage rather than wealth and rates its planning areas "mittel". The expectation was written before the land values existed. With them, Grunewald ranks #19 of 143 and the case is now a normal ground-truth check.

## 7. Definition of Done

- [x] A user opens the app and clicks **Berlin Neighborhoods** in the menu (header on desktop and mobile, also in the footer).
- [x] They see the list of neighborhoods on the left (below on mobile) and an OSM map on the right (above on mobile).
- [x] Clicking a neighborhood on the map makes the sidebar react: the row is selected, scrolled into view and expanded with its details.
- [x] The neighborhoods are ranked (#1–#143, score, top/bottom-20% badges, colour bands on the map).
- [x] A category switcher re-ranks the list and recolours the map: crime, wealth (affluence), education, amenities and seven more, plus a weighted overall score.

All five are exercised by the first Playwright journey (`e2e/neighborhoods.spec.ts`) on desktop and mobile.
