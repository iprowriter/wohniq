# ADR-0010 — Lifestyle Match: official-data region profiles with provenance

**Status:** Accepted (Step 1 of Lifestyle Match) · **Date:** 2026-11-09

## Context

Lifestyle Match recommends Berlin neighbourhoods from a short questionnaire: answers become weights, weights × neighbourhood profiles give a ranked list (the ADR-0001 principle — code does the logic). Every suggestion must be explained *with the data behind it*, so the profile data has to be real, sourced and reproducible — not the plausible-but-synthetic figures in `data/kieze.py`, which are fine for generating listings but can't back a claim like "safer than the Berlin average".

Two questions: **what unit** to profile, and **how to keep every number traceable**.

## Decision

1. **Unit = LOR Bezirksregion (143 regions, all of Berlin).** The crime atlas publishes per Bezirksregion, and the population register per LOR-Planungsraum (542), which nests exactly into Bezirksregionen. Joining on the LOR key needs no estimation, and the build verifies that it matches 143 of 143. This replaces the 14 listing Kieze as the unit of recommendation. The Kieze remain the listing inventory: each region carries `listing_kiez` when it lies in that Ortsteil (strict, hand-curated in `data/lifestyle/region_meta.py`) for the "See flats here" hand-off.
2. **Every figure carries provenance.** A `Measure` is `{raw, unit, source_id, year, method}`. Sources live in a registry (`data/lifestyle/sources.py`) with publisher, URL, licence, period and a user-facing caveat. The bundle records the SHA-256 of every raw input it was built from.
3. **Build once, load read-only.** `data/lifestyle/build_profiles.py` (`make lifestyle-data`) parses the official XLSX/PDF/GeoJSON plus the OSM GeoPackage and VBB GTFS, and writes a deterministic `regions.json` (no timestamps; sorted keys). The API loads and validates it (Pydantic) at startup. The parsing libraries (openpyxl, pypdf, pdfplumber) are dev-only and stay out of the runtime image. The raw files are not committed.
4. **Measured from where people live.** Planungsraum values are aggregated to Bezirksregionen weighted by residents. For walking-distance measures, a 100 m grid over OSM residential land gives "doorstep" sample points; each PLR's residents are spread over its points. Counts (cafés within 500 m, …) and distances (nearest water/forest, nearest rail or tram stop) are averaged over them. Region centre points (used for commute) are the resident-weighted mean of these homes, not the middle of a park or rail yard (e.g. Tiergarten Süd).
5. **Fixed normalisation.** Scores map raw values to 0..1 against fixed reference points stored in the bundle at build time, never recomputed per request. Continuous measures use the Berlin-wide 10th/90th percentiles; class-based measures use the class bounds 1..3. Amenity counts are log-scaled, because going from 2 to 10 cafés matters more than from 100 to 130. So removing or filtering regions cannot change another region's score, which matters because users can remove suggestions.
6. **Availability derived from data.** The attribute catalogue (`lifestyle/attributes.py`) lists all attributes, including those whose data hasn't arrived (with `requires`). An attribute is *available* iff the bundle has a reference range for it, so the catalogue and the data can't drift.
7. **No LLM in this feature.** Questionnaire, persona and explanations are deterministic templates. This avoids sending answers to a third party (Gemini free tier) and keeps results reproducible. A later, optional "polish" may only ever receive non-identifying attribute ids.

### Data ethics

- From the population register we read **only totals and age groups**. The `Ausländer` and `weiblich` columns are discarded at parse time, and the migration-background tables are never opened. No attribute is derived from nationality or ethnicity, because area scores built on that would be a proxy for discrimination.
- The Umweltgerechtigkeitsatlas's **social-disadvantage indicator** is read only to verify each table row's checksum, then dropped. Scoring areas on poverty indicators would stigmatise neighbourhoods. Tests enforce both exclusions.
- **Safety** uses the police *Kieztaten* rate (neighbourhood-related offences such as assault, threats, robbery, burglary and vandalism of cars; definition in the Kriminalitätsatlas foreword), averaged over 2023–2025, rather than all offences. The all-offences rate is dominated by visitors in central areas (e.g. Regierungsviertel ≈ 46,000 per 100k vs. 12,900 Berlin-wide in 2025). The police themselves note that a high rate can also reflect liveliness and popularity; the UI states this next to the number. Rankings are stable year to year (r = 0.95 between 2023 and 2025).

## Current coverage

| Attribute / field | Source | Status |
|---|---|---|
| `safety` | Kriminalitätsatlas 2023–2025 | ✅ 143 regions |
| `family` (% under 18), `young_crowd` (% 18–27) | Einwohnerregister 31.12.2024 | ✅ 143 regions |
| `quiet`, `clean_air`, `cool_summer`, `green` | Umweltgerechtigkeitsatlas 2023/24 (noise 2022, air 2023, heat 2022, green 2020) | ✅ 143 regions |
| Centre point, area, density, inner-city share | LOR 2021 Planungsräume + OSM residential land | ✅ 143 regions (enables `commute`) |
| Rent (`affordability`) | IBB Tabellenband 2025, Tab. 25: district median asking rent + 80% range; operating costs 2024 | ✅ 12 districts |
| Student budget references | Moses Mendelssohn Institut SoSe 2025 (WG room €650), BAföG €380 | ✅ city figures |
| `cafes`, `everyday`, `nightlife`, `culture`, `sport`, `water` | OSM (Geofabrik, 2026-11-08) | ✅ 143 regions |
| `transit` | VBB GTFS weekday-peak network (rail, S, U, tram) | ✅ 143 regions |

**Rent: district medians, not a finer model.** We tried blending the IBB inner/outer-city medians with each region's Innere-Stadt share, and scaling that within districts to match the district median. It produced implausible results: Alt-Treptow above central Mitte, and Wedding above Mitte's median. The official data doesn't support sub-district rents, so we use the district median and show the district's 80% offer range next to it, rather than invent precision.

**Reviewed and not used.** The strategic noise map (Umweltatlas 07.05.1, 2022) is a printed map without area statistics. The Umweltgerechtigkeitsatlas supersedes it for our purpose, with a resident-weighted noise class per Planungsraum derived from the same 2022 noise mapping.

**Verification.** The register PDF is parsed with pypdf and cross-checked against poppler's `pdftotext` (identical for all 143 regions). The Umweltgerechtigkeit table is parsed by glyph x-position with pdfplumber, with a per-row checksum (the "Mehrfachbelastung" count must equal the number of high cells); it was cross-checked against `pdftotext` (identical for all 541 rows). Geometry is checked against the published area of every Planungsraum and against the police foreword (Helmholtzplatz 0.71 km², ≈32,000 residents/km²).

**Erratum in the source.** The atlas prints Charlottenburg's row `04300414` a second time under Steglitz, in place of `06100102`. The parser checks keys against their district section, skips the duplicate, and leaves `06100102` unscored rather than guessing.

**Listing hand-off must use coordinates.** Placing the 100 synthetic listings in the LOR polygons shows that 23 lie outside the Ortsteil their `kiez` label implies (the generator scatters points around Kiez centres, e.g. "Treptow" flats inside Friedrichshain). The results page will therefore match listings to regions by point-in-polygon, not by `listing_kiez`.

## Alternatives considered

- **Keep the 14 synthetic Kieze:** rejected. Too coarse, the figures aren't sourced, and students near TU Berlin would get "Charlottenburg" rather than a specific area.
- **Ortsteile (96):** no official crime or age data at that level without area-weighted estimation.
- **LOR-Planungsräume (542):** crime isn't published at that level, and names are too granular for users.
- **Min–max normalisation over the current result set:** rejected. Scores would shift when a user removes an area.

## Consequences

- **+** Every number in an explanation traces to a publication, period and method; the build is reproducible (a test rebuilds from raw files when present).
- **+** All of Berlin is covered, including areas without WohnIQ listings (the UI says so honestly).
- **−** OSM and VBB change continuously; numbers shift slightly with each rebuild (inputs are pinned by SHA-256). The scoring engine must still treat a missing attribute as inactive, not as zero.
- **−** Walking distances are straight lines from homes, so real walks are a little longer. The caveat says so.
- **−** Environmental classes are Berlin-relative (quartile-based), not absolute health thresholds, and the green-space data is from 2020. The UI says so.
- **−** Rents are per district (12 values), so neighbourhoods within a district share a figure. The 80% offer range is shown to make the spread visible.
