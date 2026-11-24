# Berlin open data — build

The data behind the rent check, "Around this flat" and "Right now" (ADR-0016). Nothing here is
committed except code and checksums: the raw files come from a Berlin Visualized checkout, and
the build output (`build/`) is gitignored.

```bash
make berlin-data     # raw files → build/ (≈ 45 s); offline demo mode reads build/ directly
make migrate         # once: migration 0003 (PostGIS + berlin_* tables)
make berlin-load     # build/ → Supabase (≈ 15 s; replaces the berlin_* tables in one transaction)
```

The raw folder defaults to `../berlinvisualized/data/raw` next to this repo; set
`BERLIN_RAW_DIR` to use another. Every file is checked against the SHA-256 in
[`sources.py`](sources.py) before it's read, and the build stops on any mismatch.

## Inputs

| Source id (Berlin Visualized) | Publisher | Used for |
|---|---|---|
| `living.rent_index_table_2026` | SenSBW — Berliner Mietspiegeltabelle 2026 | 189 rows: range and mean €/m² by location, building age, size |
| `living.rent_index_mietspiegel_2026` | SenSBW — Mietspiegel 2026 brochure, No. 10–11 | The 83-item checklist (Orientierungshilfe) |
| `living.rent_index_residential_location_2026` | SenSBW — Wohnlagenverzeichnis 2026 (Geoportal) | 400,505 addresses: location class, East/West |
| `mobility.bvg_stations` | VBB (via transport.rest) | 2,970 Berlin stops |
| `living.schools` | SenBJF (Geoportal) | 929 schools by type |
| `living.daycare_centers_2025-11` | SenBJF — Kitaliste Nov 2025 | 2,913 Kitas with permitted places (UTM33 → WGS84) |
| `living.parks` | SenMVKU — Grünanlagenbestand (Geoportal) | 863 green spaces of 1 ha or more |
| `living.playgrounds` | SenMVKU — Spielplatzbestand (Geoportal) | 1,886 playgrounds |
| `environment.air_quality_stations_luftdaten` | SenMVKU — BLUME network | 15 stations |
| `snapshots.air_quality_index_latest` | SenMVKU — LQI | Index per station (snapshot 2026-11-15 15:00) |
| `mobility.traffic_accidents_2025_berlin` | Statistische Ämter — Unfallatlas 2025 | 13,280 accidents with injuries |
| `society.crime_atlas_2016-2025` | Polizei Berlin — Kriminalitätsatlas | Neighbourhood offences per 100,000, per district region (2023–2025 mean) |
| `boundaries.lor_planning_areas_2021` | SenSBW — LOR 2021 | 542 planning areas (comparisons, outlines) |
| `boundaries.lor_district_regions_2021` | SenSBW — LOR 2021 | 143 district regions (crime) |

Optional: the VBB timetable extract in `backend/data/vbb/` (`make demo-stops`) types each stop
(S-Bahn, U-Bahn, tram, bus, ferry, regional train) by matching name + distance. Without it,
stops are labelled "Stop". With the 2026-11-12 extract: 2,870 of 2,970 stops typed; the rest
(night-only or rarely served stops outside the 07:00–09:00 peak window) show "Stop".

Not loaded, by design ("describe areas, don't judge them"): population, election and
social-monitoring data.

## Output (`build/`)

| File | Content |
|---|---|
| `manifest.json` | Build time, input checksums, counts (written last: marks a complete build) |
| `rent_table.json`, `checklist.json` | Mietspiegel rows + building-age periods; checklist items (German text) |
| `addresses.csv.gz` | id, street, house number, postcode, district, location class, East, planning area, lat/lng, search key (sorted by key; ids follow that order) |
| `areas.json` | Planning areas and district regions (outlines simplified to 3 m), crime rates |
| `stops.json`, `schools.json`, `kitas.json`, `parks.json`, `playgrounds.json`, `air.json`, `accidents.csv.gz` | The point and park layers |
| `area_stats.json` | For each planning area, the median of every measure in `berlin/measures.py` over up to 60 of its addresses |
