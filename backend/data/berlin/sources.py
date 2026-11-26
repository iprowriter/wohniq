"""Source registry for the Berlin open data (rent check, Around this flat, Right now).

Every raw file `make berlin-data` reads, with the SHA-256 it was built from. The files
themselves live in a Berlin Visualized checkout (`BERLIN_RAW_DIR`, default
`../berlinvisualized/data/raw`, where they are documented in `data/sources.json`); they are
never committed here (ADR-0016). Only derived figures ship, with the attribution below.

`licence=None` means the publication we used doesn't state one; we use derived figures only,
with attribution.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_DIR = REPO_ROOT.parent / "berlinvisualized" / "data" / "raw"
VBB_DIR = Path(__file__).resolve().parents[1] / "vbb"  # `make demo-stops` (optional input)


@dataclass(frozen=True)
class Source:
    id: str  # same id as in Berlin Visualized's sources.json
    file: str  # path under the raw dir
    sha256: str
    title: str
    publisher: str
    licence: str | None
    data_year: str
    used_for: str
    label: str  # the short source label shown next to a figure in the UI


SOURCES: tuple[Source, ...] = (
    Source(
        "living.rent_index_table_2026",
        "living/rent_index_table_2026.pdf",
        "b1917242aaa52f3142d7516b09222b26ed252d2c22fc7c239a853c485b2819ed",
        "Berliner Mietspiegeltabelle 2026",
        "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin",
        None,
        "2026 (reference date 1 Sep 2025)",
        "Index range and mean (net cold rent per m²) by location class, building age and size.",
        "Mietspiegel 2026",
    ),
    Source(
        "living.rent_index_mietspiegel_2026",
        "living/rent_index_mietspiegel_2026.pdf",
        "ff6f45de31a48067f931829b80d457b7ef62dfe414fe67f145e53242997d2556",
        "Berliner Mietspiegel 2026 (brochure), No. 10–11: Orientierungshilfe",
        "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin",
        None,
        "2026",
        "The feature checklist that places a flat within the range (5 groups, ±20 % each).",
        "Mietspiegel 2026",
    ),
    Source(
        "living.rent_index_residential_location_2026",
        "living/rent_index_residential_location_2026.geojson",
        "f51890f6e9aca2c537b7786681aba148e2cae6d93749def4f0dfe4489b5926d0",
        "Wohnlagenverzeichnis zum Berliner Mietspiegel 2026 (address points)",
        "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin (Geoportal Berlin)",
        "Datenlizenz Deutschland – Zero – 2.0",
        "2026",
        "Location class (simple/medium/good) and East/West of every residential address.",
        "Mietspiegel",
    ),
    Source(
        "mobility.bvg_stations",
        "mobility/bvg_stations.geojson",
        "a5247d410b61ce36b0629d028b470c2265c4259ee73292e6d706e8d1c2228d19",
        "VBB stops and stations (via transport.rest)",
        "VBB Verkehrsverbund Berlin-Brandenburg GmbH",
        "ISC (API) / VBB open data",
        "2026",
        "Stops in Berlin with their location, for nearest stops and walking minutes.",
        "VBB",
    ),
    Source(
        "living.schools",
        "living/schools.geojson",
        "61237c60efdc9cd90210afde5a6201f71cc7380115472ed4540205a889d2e99e",
        "Schulen in Berlin (school directory)",
        "Senatsverwaltung für Bildung, Jugend und Familie (Geoportal Berlin)",
        "Datenlizenz Deutschland – Zero – 2.0",
        "School year 2026/27",
        "Schools within 1 km, by type.",
        "Senate",
    ),
    Source(
        "living.daycare_centers_2025-11",
        "living/daycare_centers_2025-11.xlsx",
        "f5681eff47d1ea950c8c7263e8047dc9f1535aec9c36aade51e415ac841c2b06",
        "Kitaliste Berlin, November 2025",
        "Senatsverwaltung für Bildung, Jugend und Familie",
        "CC BY",
        "November 2025",
        "Kitas within 500 m and their permitted places.",
        "Senate",
    ),
    Source(
        "living.parks",
        "living/parks.geojson",
        "9fd58a29c9ee6b9bcc6651dab6ce6beaa7913352fdd99ad5158d70f6b45608f2",
        "Grünanlagenbestand Berlin (public green spaces)",
        "Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (Geoportal Berlin)",
        "Datenlizenz Deutschland – Zero – 2.0",
        "2026",
        "Nearest green space of 1 ha or more.",
        "Geoportal",
    ),
    Source(
        "living.playgrounds",
        "living/playgrounds.geojson",
        "c10d42bacbf45a5a58bdd0c5b8f68f709bac39ece118aec326eaee4890719c5e",
        "Spielplatzbestand Berlin (public playgrounds)",
        "Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (Geoportal Berlin)",
        "Datenlizenz Deutschland – Zero – 2.0",
        "2026",
        "Playgrounds within 500 m.",
        "Geoportal",
    ),
    Source(
        "environment.air_quality_stations_luftdaten",
        "environment/air_quality_stations_luftdaten.geojson",
        "46ff88f6acff58101479fa6504bb5fd8214d76847831021982cf5fa55aef18ad",
        "Berliner Luftgüte-Messnetz (BLUME) — stations",
        "Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (luftdaten.berlin)",
        "Datenlizenz Deutschland – Zero – 2.0",
        "2026",
        "Location and type of the nearest air-quality station.",
        "luftdaten.berlin",
    ),
    Source(
        "snapshots.air_quality_index_latest",
        "snapshots/air_quality_index_latest.json",
        "8f83e759513aa9875014b82dc958998f437bd197c7c7a5f9d7892b4fb029b037",
        "Berliner Luftqualitätsindex (LQI) — snapshot",
        "Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt (luftdaten.berlin)",
        "Datenlizenz Deutschland – Zero – 2.0",
        "Snapshot of 2026-11-15, 15:00",
        "The air-quality index (1 very good – 6 very poor) at the nearest station.",
        "luftdaten.berlin",
    ),
    Source(
        "mobility.traffic_accidents_2025_berlin",
        "mobility/traffic_accidents_2025_berlin.csv",
        "809ee3d6d3042fd6d41e5f56b1f9cab58c0f849e9e1817ee1cdb5fc9b49df426",
        "Unfallatlas — Unfallorte 2025 (Berlin)",
        "Statistische Ämter des Bundes und der Länder",
        "Datenlizenz Deutschland – Namensnennung – 2.0",
        "2025",
        "Road accidents with personal injury within 300 m.",
        "Unfallatlas",
    ),
    Source(
        "society.crime_atlas_2016-2025",
        "society/crime_atlas_2016-2025.xlsx",
        "8f02cee9b1b0709eb06e39bebfe8751f69058ca535f1d1bfb86e006261f872bc",
        "Kriminalitätsatlas Berlin 2016–2025",
        "Polizei Berlin (LKA), Polizeiliche Kriminalstatistik",
        None,
        "2023–2025",
        "Neighbourhood offences per 100,000 residents, per district region (same figures "
        "as Berlin Neighbourhoods).",
        "Police atlas",
    ),
    Source(
        "boundaries.lor_planning_areas_2021",
        "boundaries/lor_planning_areas_2021.geojson",
        "ae03672c4173a677fdd0f0c518aae99e0b461514428a2b59d037de1b73d47050",
        "Lebensweltlich orientierte Räume (LOR) 2021 — Planungsräume",
        "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin",
        "CC BY 3.0 DE",
        "2021",
        "The 542 planning areas each figure is compared with.",
        "LOR 2021",
    ),
    Source(
        "boundaries.lor_district_regions_2021",
        "boundaries/lor_district_regions_2021.geojson",
        "4bbd07fcba592d0f4e32def7b5949cb90437894dd7a711a6e413e52ed502ec7d",
        "Lebensweltlich orientierte Räume (LOR) 2021 — Bezirksregionen",
        "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin",
        "CC BY 3.0 DE",
        "2021",
        "The 143 district regions used for recorded crime.",
        "LOR 2021",
    ),
)

BY_ID: dict[str, Source] = {s.id: s for s in SOURCES}

# The offline base map (Protomaps basemap v4 from OpenStreetMap, z0–15, Berlin), next to
# the raw folder in Berlin Visualized (data/map). Copied into the build and served by the
# API at /tiles/berlin.pmtiles; every map in the app draws from it (ADR-0019).
MAP_FILE = "berlin.pmtiles"
MAP_SHA256 = "3b744d4725ff31e472878eb35fafc9858bab2c4d68910cccee113827a390609c"
MAP_ATTRIBUTION = "© OpenStreetMap contributors · Protomaps"


def map_path(root: Path | None = None) -> Path:
    return (root or raw_dir()).parent / "map" / MAP_FILE


# Optional input: the VBB timetable extract (`make demo-stops`) gives each stop its
# transport types. Without it every stop is labelled "Stop".
VBB_FILES = ("network_rides.csv", "network_boardings.csv", "network_stations.csv")


class SourceError(RuntimeError):
    """A raw file is missing or doesn't match its recorded checksum."""


def raw_dir() -> Path:
    return Path(os.environ.get("BERLIN_RAW_DIR") or DEFAULT_RAW_DIR)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verified_path(source_id: str, root: Path | None = None) -> Path:
    """The raw file for `source_id`, after checking it exists and matches its checksum."""
    src = BY_ID[source_id]
    path = (root or raw_dir()) / src.file
    if not path.is_file():
        raise SourceError(
            f"{src.file} not found under {path.parent.parent}. Set BERLIN_RAW_DIR to a "
            "Berlin Visualized checkout's data/raw folder."
        )
    actual = sha256(path)
    if actual != src.sha256:
        raise SourceError(f"{src.file}: checksum {actual[:12]}… ≠ recorded {src.sha256[:12]}…")
    return path
