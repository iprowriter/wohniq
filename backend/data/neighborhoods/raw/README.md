# Berlin Neighbourhoods — raw source files

The official files `make neighborhoods-data` reads. Like the Lifestyle Match raw files they
are **not committed** (size, and some publishers don't state a redistribution licence).
Only the derived figures in `../neighborhoods.json` ship, with attribution in
`../sources.py`. The SHA-256 of every input is recorded in `neighborhoods.json` under `inputs`.

The build also reads the shipped Lifestyle Match bundle (`../../lifestyle/regions.json`)
for names, population, amenities, environment classes, transit, rents and commute times,
and its simplified outlines (`../../lifestyle/regions_geo.json`), which it checks against
the official LOR areas below.

| File (glob) | Publisher | Where to get it | Used for |
|---|---|---|---|
| `fallzahlen_hz-*.xlsx` | Polizei Berlin — Kriminalitätsatlas | polizei.berlin.de → Kriminalitätsatlas "Datentabelle" (also daten.berlin.de) | Safety: 7 offence rates, mean 2023–2025 |
| `Unfallorte*_CSV.zip` | Statistische Ämter des Bundes und der Länder — Unfallatlas | unfallatlas.statistikportal.de → Open Data (CSV) | Road safety |
| `*mss2023*.pdf` | SenSBW — Monitoring Soziale Stadtentwicklung 2023, Tabelle 1 | berlin.de/sen/sbw/stadtdaten/stadtwissen/monitoring-soziale-stadtentwicklung/ | Affluence (status index per planning area) |
| `Blickpunkt_Schule*.pdf` | SenBJF — Blickpunkt Schule, Bericht 2025/2026 | bildungsstatistik.berlin.de | Education (Abb. 5.1.2, Tab. 3.2.3) |
| `berlin-*free.gpkg.zip` | © OpenStreetMap contributors (ODbL), Geofabrik | download.geofabrik.de/europe/germany/berlin-latest-free.gpkg.zip | Healthcare, schools/Kitas, parks, playgrounds, stops, parking, street length |
| `brw*_vector_*.geojson` | Gutachterausschuss für Grundstückswerte in Berlin — Bodenrichtwerte | Geoportal Berlin / BORIS Berlin (vector data, WGS84) | Affluence: land-value index at homes |
| `Statistischer Bericht*Einkommensteuer*.pdf` | Amt für Statistik Berlin-Brandenburg — SB L IV 3 – j/22 | statistik-berlin-brandenburg.de | Berlin-wide income per taxpayer (city reference) |
| `lor_2021_b_lor_bzr_2021_*.csv` / `.geojson` | SenStadt / AfS — LOR 2021 Bezirksregionen | daten.berlin.de / Geoportal Berlin | Wider-area names (Prognoseraum); outline check |

Used for the current bundle:

```
8f02cee9b1b0709eb06e39bebfe8751f69058ca535f1d1bfb86e006261f872bc  fallzahlen_hz-2016-2025.xlsx
f4b11dba79abaa8d14dd780a5e7f4e504454946f784d2236ef79607e2ec58dac  Unfallorte2025_EPSG25832_CSV.zip
382e0d6e6f2b18e092ef20797236e6145071b639cb80b584dd2ef8af8d20dc0c  1sdi_mss2023.pdf
3b8762198e8582b7e1e4bf18b73bde97401ca9beb70965fb5a73c6f198558fea  Blickpunkt_Schule.pdf
4d5e323a0e4f9c29df0478f1df040b9dec56ef31af0486732f4311620198238d  berlin-261112-free.gpkg.zip   (OSM data as of 2026-11-12)
8716cf84008bf2c7d3aa64346d06423bb59c1fcd284a22e5105f2e96d3bf5b14  lor_2021_b_lor_bzr_2021_WGS84.csv
7f61dc5aaf2fbdecfdf2b3a912732f520fcb37b3c3a21512f9888b4eeabc8926  lor_2021_b_lor_bzr_2021_WGS84.geojson
55e5d8c6d878579a3632f172032fc614a82615dea1e82f44531bc6122334ab9a  brw2026_brw2026_vector_WGS84.geojson  (reference date 2026-01-01)
d82e1d4538668d95c6161e89fbaa03c053237bdfa5a4e089864b93908ac611e4  Statistischer Bericht "Lohn- und Einkommensteuer im Land Berlin.pdf  (L IV 3 – j/22)
```

## Income: not published per neighborhood

- `Statistischer Bericht "Lohn- und Einkommensteuer im Land Berlin.pdf` (L IV 3 – j/22) is parsed, but it covers **Berlin as a whole only**. No table breaks income down by Bezirk, and district results can't be obtained.
- The page therefore shows: "Not published per neighborhood. Berlin-wide: €45,161 per taxpayer (2022)". `income` keeps its `requires` note in `neighborhoods/catalog.py` and is never scored.
- Not used as inputs: `Lohn- und Einkommensteuer im Land Berlin.pdf` (the metadata document) and `brw-erlaeuterung-2025.pdf` (the Bodenrichtwert explanations; its § 4 is why land is only compared within the same density class).

## Checks the build performs

- Crime: the Kieztaten rates must equal the Lifestyle bundle's `safety` figures (same source).
- MSS: each row's class number must match its label; 542 planning areas summing to ~3.85 M residents.
- Schools: the chart numbers must reproduce the percentages the report's text quotes
  (e.g. Abitur 60.1% in Steglitz-Zehlendorf, 28.5% in Marzahn-Hellersdorf; 8.7% Berlin-wide
  without a qualification).
- Outlines: every simplified region outline within 2% of the official LOR area.
- Accidents: at least 99% of Berlin's accidents must fall inside a region.
- Land values: one reference date, a value for every residential zone, unique zone ids; every region must have home points inside residential zones.
- Income report: the brackets must add up to the total (taxpayers exactly, income within rounding); each row's change column must match its values.
