# ADR-0013 — Berlin Neighborhoods: ranked area profiles from official data

**Status:** Accepted (M8) · **Date:** 2026-11-13 · **Amends:** the data-ethics section of [ADR-0010](0010-lifestyle-match-data-model.md) for this feature

## Context

Users asked for a page that shows all of Berlin's major neighbourhoods on a map, with crime, income/wealth, amenities (hospitals, schools, cafés), parks, parking, road accidents and education, and that ranks them by any one category ("which areas have the least crime, which to be careful about").

Lifestyle Match (ADR-0010/0011) already holds sourced profiles for the 143 LOR *Bezirksregionen*. But it ranks for one person's answers and deliberately leaves out socio-economic indicators. This feature is a different product: a neutral, browsable comparison of every area on every category.

## Decision

1. **Same unit, same outlines.** The 143 LOR Bezirksregionen (ADR-0010): the finest level with official crime data, with the Lifestyle bundle's display names and simplified outlines. Each area also shows its *Prognoseraum* (e.g. "Kreuzberg Nord") so people recognise where it is. The build checks every outline against the official LOR area (max deviation 0.82%).

2. **A separate bundle, built reproducibly** (`make neighborhoods-data` → `data/neighborhoods/neighborhoods.json`). It reuses the Lifestyle bundle's figures and adds parsed official files:
   - **Kriminalitätsatlas:** 7 offence rates, mean 2023–2025.
   - **Unfallatlas 2025:** 13,280 injury accidents, placed by coordinates.
   - **MSS 2023:** status class of each of 542 planning areas, resident-weighted.
   - **Blickpunkt Schule 2025/26:** district school-leaver qualifications and Gymnasium recommendations.
   - **OpenStreetMap:** hospitals, doctors, pharmacies, schools, Kitas, playgrounds, parks, stops, parking-ticket machines, car parks and street length, measured from 100 m home sample points as in ADR-0010.

   Every value carries `{raw, source_id, year, method}`. Every parser checks itself against figures the publication states: the report's quoted percentages, class/label agreement, the population total, and the Kieztaten figures matching the Lifestyle bundle. The raw SHA-256s are recorded, and `make test-all` rebuilds and compares byte for byte.

3. **Scoring is percentile-based against a fixed distribution.** A metric's score is the share of Berlin's 143 areas the area does better on (ties count half), read against the sorted distribution stored in the bundle.
   - Percentiles are robust to outliers. Tiergarten Süd's crime rate is 2.6× Berlin's and doesn't squash everyone else, which min–max scaling would. They also mean the same thing for every metric.
   - Category score = weighted mean of its metrics (weights in `neighborhoods/catalog.py`).
   - Overall = weighted mean of categories; weights 0–3, user-adjustable, with safety counted double by default.
   - Ranks are competition ranks (ties share a rank) and always Berlin-wide; filtering the list never changes them.
   - The top/bottom 20% get the category's labels ("Lowest crime" / "Highest crime").
   - No LLM anywhere (ADR-0001).

4. **Socio-economic data, with guard-rails (amends ADR-0010 for this feature).** The product owner asked for wealth and education categories and accepted this plan. We use:
   - **Affluence:** the Senate's MSS status index (built from indicators such as unemployment and welfare receipt), resident-weighted.
   - **Education:** district school results plus nearby schools and Kitas.

   Guard-rails:
   - **Named as proxies.** The categories are called "Affluence" and "Education", and the UI says what they are not: median wealth and literacy aren't published for neighbourhoods in Germany.
   - **Labels describe the measure, not people:** "Highest status / Lowest status", "Strongest / Weakest education". No category tells users to "avoid" an area. The eval scans every label and every generated sentence for banned wording.
   - **Caveats travel with the data.** Each category carries one (busy-centre crime, district-level school data counted where the school is, OSM completeness), shown above the list and in "About this data".
   - **Still excluded:** nationality or migration data; the register isn't an input of this build.

5. **Pending metrics are first-class.** `income` (income per taxpayer by district) and `land_value` (Bodenrichtwerte) are declared in the catalogue with `requires`. The API lists them and the UI shows "coming when the data arrives". They are never scored as zero. The bundle validator refuses a pending metric that has data, so enabling one is an explicit change.

6. **Read-only API, no database** (`/api/v1/neighborhoods/{catalog,ranking,areas/{key},regions.geojson}`). Requests carry only a category and optional weights (no personal data), so responses are cacheable GETs and the feature works unchanged in offline demo mode.

## Evaluation

`make eval-neighborhoods` (also run by pytest) — 65/65 checks, plus 1 reported known gap:

- **Ground truth (13 cases)** written from well-known facts, not fitted to output:
  - visitor hubs (Alexanderplatz, Regierungsviertel, Tiergarten Süd) rank in the bottom 20% for safety; Müggelheim, Frohnau and Kladow in the top 20%;
  - Prenzlauer Berg has the hardest parking;
  - every Marzahn-Hellersdorf area ranks as more affordable than every Mitte area;
  - Steglitz-Zehlendorf beats Marzahn-Hellersdorf on education.
- **Properties:**
  - determinism;
  - direction (a better raw value never scores lower);
  - dominance within a category;
  - monotonicity of overall weights;
  - "only one category weighted" equals that category's ranking;
  - tier sizes;
  - grounded highlights (each quotes its stored number, true rank and a registered source);
  - provenance;
  - wording.
- **Known gap (reported, not hidden):** Grunewald isn't in the top 20% for Affluence. The MSS rates all four of its planning areas "mittel": the index measures disadvantage, so it doesn't separate affluent from average areas. Income or land-value data should close this, and the eval flags the case when it starts passing.
- **One case was corrected, not the data.** The first draft expected Müggelheim to be among the quietest areas. It lies under the BER approach paths, and the atlas's noise class includes aircraft noise.

## Alternatives considered

- **Min–max or 10th/90th-percentile linear scaling (as in Lifestyle Match):** rejected for ranking. Clipping ties up to 10% of areas at each end and makes ranks arbitrary among them. Min–max lets one outlier compress everyone else.
- **Ortsteile (96):** better-known names, but no official crime data at that level.
- **District-level only (12):** too coarse. Every Prenzlauer Berg area would equal Buch.
- **Income from the tax statistics' metadata PDF:** that document has no figures. It is listed as still needed.

## Consequences

- **+** Every number on the page links to a publication, period and method; rankings are reproducible and explainable.
- **+** The same percentile yardstick across 38 metrics makes categories comparable and the overall weights meaningful.
- **−** District-level metrics (rent, school results) give all areas of a district the same value. The UI labels them "district figure".
- **−** The Affluence proxy is coarse (4 classes) until income or land values are added. This is documented and tracked by the eval's known gap.
- **−** OSM-based counts depend on mapping completeness (parking especially). The caveats say so.

## Addendum (2026-11-13) — land values and the income report

**Land values (Bodenrichtwerte 01.01.2026, Gutachterausschuss Berlin, 1,623 zones).** `land_value` is no longer pending:

- Each home sample point takes the value of the residential, core or mixed zone it lies in (899 zones; commercial, special-use, farm and forest zones are left out).
- It is compared only with zones of the same density class: houses at GFZ ≤ 0.7 (including W-EFH), or flats. The Gutachterausschuss states that converting values between these sub-markets is "fachlich unzulässig", and its GFZ conversion coefficients don't bridge them.
- The index is the mean of those percentiles (0–100). The median EUR/m² is shown as context (weight 0), because raw EUR/m² mostly measures permitted density: the Regierungsviertel at €8,500 and Prenzlauer Berg at €5,000 sit above Grunewald at €2,700.
- Within Affluence, status index, land-value index and (pending) income get **equal weights**. Each measures a different facet (disadvantage, property prices, income), and nothing justifies ranking one above another.

**Income (Statistischer Bericht L IV 3 – j/22).** The report has Berlin-wide tables only; "Bezirk" doesn't occur in it.

- Table 1 is parsed from glyph positions. Thin spaces inside numbers are 1.5 pt; column gaps are ≥ 5 pt.
- Checks: the brackets must add up to the total (taxpayers exactly, income within rounding), and every change column must match its two values.
- It provides the Berlin reference, €45,161 total income per taxpayer (2022), shown next to the still-pending `income` metric. `income` stays pending until district results exist.

**Result.** The eval's known gap (Grunewald not in the Affluence top 20%) closed on its own with the new data (#19 of 143) and was promoted to a normal ground-truth case. 65/65 checks pass, with no known gaps.

## Addendum 2 (2026-11-13) — income is not published per neighborhood

District income-tax results can't be obtained. `income` is therefore no longer presented as "coming": its note reads "Not published per neighborhood", and the UI shows "Not published per neighborhood. Berlin-wide: €45,161 per taxpayer (2022)", with its source. It remains unscored. Affluence is the social-status index plus the land-value index, with equal weights.
