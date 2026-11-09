# Lifestyle Match — raw source files

The official files `make lifestyle-data` reads. They are **not committed** (size, and
some publishers don't state a redistribution licence). Only the derived figures in
`../regions.json` ship, with attribution in `../sources.py`. The SHA-256 of every input
used for the current bundle is recorded in `regions.json` under `inputs`.

| File (glob) | Publisher | Where to get it | Used for |
|---|---|---|---|
| `fallzahlen_hz-*.xlsx` | Polizei Berlin — Kriminalitätsatlas | polizei.berlin.de → Kriminalitätsatlas "Datentabelle" (also on daten.berlin.de) | `safety` |
| `SB_A01-16-00_*_BE.pdf` | Amt für Statistik Berlin-Brandenburg | statistik-berlin-brandenburg.de → Statistischer Bericht A I 16 "Einwohnerregisterstatistik Berlin" (LOR-Planungsräume) | `family`, `young_crowd`, population |
| `lor_2021_a_lor_plr_2021_*.geojson` | SenStadt / AfS — LOR 2021 Planungsräume (WGS84) | daten.berlin.de / Geoportal Berlin → "Lebensweltlich orientierte Räume 2021" | centre points, area, density, Innere/Äußere Stadt → rent estimate, commute |
| `umweltgerechtigkeitsatlas_*broschuere.pdf` | SenMVKU — Umweltgerechtigkeitsatlas 2023/2024 | berlin.de/umweltatlas → Umweltgerechtigkeit → Broschüre | `quiet`, `clean_air`, `cool_summer`, `green` |
| `berlin-*free.gpkg.zip` | © OpenStreetMap contributors (ODbL), Geofabrik extract | download.geofabrik.de/europe/germany/berlin-latest-free.gpkg.zip (rename keeps the date, e.g. `berlin-261108-free.gpkg.zip`) | `cafes`, `everyday`, `nightlife`, `culture`, `sport`, `water`; residential land for home-based centre points |
| `*gtfs*.zip` | VBB Verkehrsverbund Berlin-Brandenburg | vbb.de/vbbgtfs (same file `make demo-stops --from-zip` reads) | `transit` (rail/tram stops in the weekday-peak network) |

Used for the current bundle:

```
8f02cee9b1b0709eb06e39bebfe8751f69058ca535f1d1bfb86e006261f872bc  fallzahlen_hz-2016-2025.xlsx
a39fabb2fc69e85983d138ae2237d291ba2114fdbb2f985bada1ad4b011cb646  SB_A01-16-00_2024h02_BE.pdf
4dbd67e4fe63090bf7802e61e6fe1e6c01db5ce23c377f211276404fd3038382  lor_2021_a_lor_plr_2021_WGS84.geojson
6aad84a8676ea60d7289adc55b7b2a6f24f19e64792323e437b2e1a729d9d29c  umweltgerechtigkeitsatlas_2023-2024_broschuere.pdf
b4b912e4ea1d1ff08c51a6249737796249135c3d85aa01aa139d0a1ed3fdd2ec  berlin-261108-free.gpkg.zip   (OSM data as of 2026-11-08)
d962592456cd7e39c9162ba22aff8f44f87d90b5d54303fee6a6506a758c4df7  vbb_gtfs.zip                  (feed of 2026-11-05)
```

The OSM and VBB files change daily/weekly upstream. A rebuild with newer files gives
slightly different numbers; `inputs` in `regions.json` records exactly which ones were used.

Berlin-wide and district figures (IBB Wohnungsmarktbericht 2025 summary and
Tabellenband Tab. 25, Berliner Betriebskostenübersicht 2026, Moses Mendelssohn Institut
SoSe 2025) are transcribed in `../sources.py` with page references, so their PDFs
aren't needed for the build. The Kriminalitätsatlas foreword (definition of
"Kieztaten") is cited in the source caveat.

## Known issue in the Umweltgerechtigkeitsatlas 2023/2024

In the appendix table, the Steglitz-Zehlendorf section prints a row keyed `04300414`
(Charlottenburg's "Schloßstraße", identical values) where `06100102` (Steglitz's
"Schloßstraße") should be. The parser checks every key against its district section,
skips that row and reports it. `06100102` therefore has no environmental classes, and
the region 061001 is scored on its other planning areas (coverage is in each measure's
`method`).

## Coverage

All 14 area attributes are built for all 143 regions. The build takes about two minutes
(`make lifestyle-data`); `make test-all` rebuilds and checks the result is identical.
