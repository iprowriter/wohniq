"""Build the Lifestyle Match profile bundle (`data/lifestyle/regions.json`).

Reads the official source files from a local raw directory (not committed; see
raw/README.md for where to download them), joins them on the LOR Bezirksregion key,
and writes a small, validated, deterministic JSON bundle that the API loads at runtime.

    uv run python -m data.lifestyle.build_profiles [--raw-dir PATH] [--out PATH]

Inputs:
  * Kriminalitätsatlas XLSX       -> safety ('Kieztaten' HZ, mean of 2023–2025)
  * Einwohnerregister PDF         -> family, young_crowd, population (Tabelle 2, age groups)
  * LOR 2021 Planungsräume GeoJSON -> area, centre points, Innere/Äußere Stadt
  * Umweltgerechtigkeitsatlas PDF -> quiet, clean_air, cool_summer, green (class per PLR)
  * OSM GeoPackage (Geofabrik)    -> cafes, everyday, nightlife, culture, sport, water
  * VBB GTFS zip                  -> transit (rail/tram stops in the weekday-peak network)
  * IBB Tabellenband / Betriebskosten / MMI -> rents and city figures (sources.py)

Planungsraum (PLR) values are aggregated to Bezirksregionen weighted by residents, so a
region's figure describes where its people live (not its parks or rail yards).

Privacy/ethics by construction: from the register we read only the total and the eight
age-group columns. The 'weiblich' and 'Ausländer' columns are dropped at parse time,
and the migration-background tables (1, 3, 4) are never opened. From the
Umweltgerechtigkeitsatlas, the social-disadvantage column is read only to verify the
row checksum and then discarded — see ADR-0010.

Every step validates its input (age groups must sum to the row total; every region must
appear in both sources) and raises instead of writing a partial bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import statistics
import tempfile
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from data.lifestyle import geo, region_meta
from data.lifestyle.access import PlrAccess
from data.lifestyle.destinations import DESTINATIONS
from data.lifestyle.sources import (
    CITY_FIGURES,
    DISTRICT_RENTS,
    IBB_TABLES,
    LOR,
    OSM,
    PKS,
    REGISTER,
    SOURCES,
    UG_ATLAS,
    VBB,
)
from lifestyle.profiles import BUNDLE_PATH, SCHEMA_VERSION, ProfileBundle
from lifestyle.shapes import SHAPES_PATH

RAW_DIR = Path(__file__).resolve().parent / "raw"
CRIME_GLOB = "fallzahlen_hz-*.xlsx"
REGISTER_GLOB = "SB_A01-16-00_*_BE.pdf"
LOR_GLOB = "lor_2021_a_lor_plr_2021_*.geojson"
UG_GLOB = "umweltgerechtigkeitsatlas_*broschuere.pdf"
OSM_GLOB = "berlin-*free.gpkg.zip"
GTFS_GLOB = "*gtfs*.zip"

CRIME_YEARS = (2023, 2024, 2025)  # LOR 2021 keys are stable across these years
CITY_KEY = "999999"
CITY_LABEL = "Berlin (PKS gesamt)"


class BuildError(RuntimeError):
    """Raised when an input doesn't look the way the builder expects."""


# --- Population register (PDF, Tabelle 2) ------------------------------------------

AGE_COLUMNS = ("u6", "a6_15", "a15_18", "a18_27", "a27_45", "a45_55", "a55_65", "a65plus")


@dataclass(frozen=True)
class PlanningAreaRow:
    """One LOR-Planungsraum: total + the eight age groups. Nothing else is kept."""

    bezirk: str
    prognoseraum: str
    bezirksregion: str
    planungsraum: str
    total: int
    ages: tuple[int, ...]  # in AGE_COLUMNS order

    @property
    def region_key(self) -> str:
        return self.bezirk + self.prognoseraum + self.bezirksregion


# Key columns, then the 11 numeric cells. In the layout text, columns are separated by
# 2+ spaces and thousands by a single space ("1 219"); "–" means zero.
_ROW = re.compile(r"^(\d{2})\s{2,}(\d{2})\s{2,}(\d{2})\s{2,}(\d{2})\s{2,}(.*)$")
_CELL = re.compile(r"^(?:\d{1,3}(?: \d{3})*|[–-])$")
_N_NUMERIC = 11  # total, 8 age groups, weiblich, Ausländer


def _to_int(cell: str) -> int:
    return 0 if cell in ("–", "-") else int(cell.replace(" ", ""))


def parse_register_lines(lines: Iterable[str]) -> list[PlanningAreaRow]:
    """Parse Tabelle-2 text lines into rows. Non-data lines are ignored.

    Raises BuildError on a data-looking line that doesn't have exactly 11 numeric
    cells, or whose age groups don't sum to its total (the built-in checksum).
    """
    rows: list[PlanningAreaRow] = []
    for line in lines:
        m = _ROW.match(line.strip())
        if not m:
            continue
        cells = re.split(r"\s{2,}", m.group(5).strip())
        if len(cells) != _N_NUMERIC or not all(_CELL.match(c) for c in cells):
            raise BuildError(f"Unexpected register row layout: {line.strip()!r}")
        total = _to_int(cells[0])
        ages = tuple(_to_int(c) for c in cells[1:9])
        # cells[9] (weiblich) and cells[10] (Ausländer) are intentionally discarded.
        if sum(ages) != total:
            raise BuildError(f"Age groups don't sum to total ({sum(ages)} != {total}): {line!r}")
        rows.append(PlanningAreaRow(*m.group(1, 2, 3, 4), total=total, ages=ages))
    return rows


def read_register_pdf(path: Path) -> list[PlanningAreaRow]:
    """Extract Tabelle 2 ('nach LOR-Planungsräumen und Altersgruppen') from the PDF."""
    from pypdf import PdfReader  # build-time dependency only

    lines: list[str] = []
    for page in PdfReader(str(path)).pages:
        text = page.extract_text(extraction_mode="layout")
        # Tabelle 2 only. Tables 1, 3 and 4 are about migration background: skipped.
        if "Altersgruppen" in text and "Migrationshintergrund" not in text:
            lines.extend(text.splitlines())
    rows = parse_register_lines(lines)
    planning_areas = {(r.region_key, r.planungsraum) for r in rows}
    if len(planning_areas) != len(rows):
        raise BuildError("Duplicate Planungsraum rows in register extract")
    if len(rows) < 500:
        raise BuildError(f"Only {len(rows)} Planungsräume parsed; expected ~542")
    return rows


# --- Crime atlas (XLSX) -------------------------------------------------------------


@dataclass(frozen=True)
class CrimeTable:
    names: dict[str, str]  # key -> official Bezirksregion / Bezirk name
    kieztaten: dict[str, dict[int, float]]  # key -> {year: HZ}


def read_crime_xlsx(path: Path, years: Iterable[int] = CRIME_YEARS) -> CrimeTable:
    """Read the 'Kieztaten' Häufigkeitszahl per Bezirksregion for each year."""
    from openpyxl import load_workbook  # build-time dependency only

    wb = load_workbook(path, read_only=True, data_only=True)
    names: dict[str, str] = {}
    values: dict[str, dict[int, float]] = {}
    for year in years:
        sheet = f"HZ_{year}"
        if sheet not in wb.sheetnames:
            raise BuildError(f"{path.name}: missing sheet {sheet}")
        rows = list(wb[sheet].iter_rows(values_only=True))
        header_idx = next(
            (i for i, r in enumerate(rows) if r and str(r[0] or "").startswith("LOR-Schlüssel")),
            None,
        )
        if header_idx is None:
            raise BuildError(f"{sheet}: header row not found")
        header = [" ".join(str(c or "").split()) for c in rows[header_idx]]
        try:
            col = header.index("Kieztaten")
        except ValueError:
            raise BuildError(f"{sheet}: no 'Kieztaten' column in {header}") from None
        for r in rows[header_idx + 1 :]:
            key = str(r[0] or "").strip()
            # The city-total row's key is missing in some editions (2023): match by label.
            if not key and str(r[1] or "").strip() == CITY_LABEL:
                key = CITY_KEY
            if not re.fullmatch(r"\d{6}", key):
                continue
            value = r[col]
            if not isinstance(value, int | float):  # "-" for unassignable rows
                continue
            names.setdefault(key, str(r[1]).strip())
            values.setdefault(key, {})[year] = float(value)
    return CrimeTable(names=names, kieztaten=values)


# --- LOR Planungsräume (GeoJSON) ----------------------------------------------------


@dataclass(frozen=True)
class PlanningArea:
    plr_id: str  # 8 digits: Bezirk+Prognoseraum+Bezirksregion+Planungsraum
    bzr_id: str
    area_m2: float  # published area ('finhalt'); the geometry is checked against it
    centroid: tuple[float, float]  # (lat, lng), area centroid
    inner_city: bool  # Senate 'Stadtraum' classification: Innere Stadt
    polygons: list = field(default_factory=list, compare=False, repr=False)


def polygon_area_centroid(geometry: dict) -> tuple[float, tuple[float, float]]:
    """Area (m²) and area centroid (lat, lng) of a GeoJSON Polygon/MultiPolygon (holes too)."""
    try:
        return geo.polygons_area_centroid(geo.geojson_polygons(geometry))
    except ValueError as exc:
        raise BuildError(str(exc)) from None


def read_lor_geojson(path: Path) -> dict[str, PlanningArea]:
    data = json.loads(path.read_text(encoding="utf-8"))
    areas: dict[str, PlanningArea] = {}
    for feature in data["features"]:
        props = feature["properties"]
        plr_id = str(props["plr_id"])
        area, centroid = polygon_area_centroid(feature["geometry"])
        published = float(props["finhalt"])
        if abs(area - published) > 0.02 * published + 100:
            raise BuildError(f"{plr_id}: computed area {area:.0f} m² vs published {published:.0f}")
        if not plr_id.startswith(str(props["bzr_id"])):
            raise BuildError(f"{plr_id}: doesn't nest into Bezirksregion {props['bzr_id']}")
        stadtraum = str(props["stadtraum_name"]).strip()
        if stadtraum not in ("Innere Stadt", "Äußere Stadt"):
            raise BuildError(f"{plr_id}: unexpected Stadtraum {stadtraum!r}")
        areas[plr_id] = PlanningArea(
            plr_id=plr_id,
            bzr_id=str(props["bzr_id"]),
            area_m2=published,
            centroid=centroid,
            inner_city=stadtraum == "Innere Stadt",
            polygons=geo.geojson_polygons(feature["geometry"]),
        )
    return areas


# --- Umweltgerechtigkeitsatlas (PDF table of ■ glyphs) ------------------------------

# Column headers of the appendix table, left to right. Each cell is 1–3 squares:
# ■ low, ■■ medium, ■■■ high burden (for green space: good / medium / poor supply).
# "Mehrfachbelastung" counts the high (■■■) cells in the row: our checksum.
UG_HEADERS = (
    "Mehrfachbelastung",
    "Lärmbelastung",
    "Luftbelastung",
    "Thermische",
    "Grünflächenversorgung",
    "Soziale",
)
UG_INDICATORS = ("quiet", "clean_air", "cool_summer", "green")  # columns 1–4
# Shares are reported as best/middle/worst so explanations read the same for every
# indicator (for green space, "low burden" would mean *good* supply — confusing).
UG_CLASS_NAMES = {1: "best", 2: "middle", 3: "worst"}


@dataclass(frozen=True)
class UgRow:
    plr_id: str
    classes: tuple[int | None, ...]  # (noise, air, heat, green); None = not reported


def decode_ug_row(runs: Sequence[tuple[float, int]], anchors: Sequence[float]) -> list[int | None]:
    """Assign ■-runs (x position, length) to columns by nearest header x; validate.

    Returns the six cells (None where empty). Raises BuildError if two runs land in one
    column, a run is far from every column, a value is out of range, or the
    Mehrfachbelastung count doesn't match the number of high (3) cells.
    """
    cells: list[int | None] = [None] * len(anchors)
    for x, n in runs:
        j = min(range(len(anchors)), key=lambda k: abs(anchors[k] - x))
        if abs(anchors[j] - x) > 20 or cells[j] is not None:
            raise BuildError(f"Can't place ■ run at x={x:.0f} (anchors {anchors})")
        cells[j] = n
    multiple, values = cells[0] or 0, cells[1:]
    if any(v is not None and not 1 <= v <= 3 for v in values) or multiple > 5:
        raise BuildError(f"Out-of-range cell in {cells}")
    if multiple != sum(1 for v in values if v == 3):
        raise BuildError(f"Checksum failed: Mehrfachbelastung {multiple} vs cells {values}")
    return cells


def district_key(name: str) -> str:
    """Letters-only upper-case district name: robust to soft hyphens and spacing."""
    return re.sub(r"[^A-ZÄÖÜ]", "", name.upper())


def _group_lines(words: list[dict], tolerance: float = 2.0) -> list[list[dict]]:
    """Group pdfplumber words into text lines by vertical position, left to right."""
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= tolerance:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def read_ug_pdf(path: Path, district_codes: dict[str, str]) -> tuple[dict[str, UgRow], list[str]]:
    """Parse the 'Aufschlüsselung der Planungsräume' table.

    `district_codes` maps `district_key(name)` (e.g. "STEGLITZZEHLENDORF") to its
    2-digit code. A row whose key doesn't belong to
    the district section it's printed in is an erratum in the publication: it is
    skipped and reported rather than trusted (2023/24 edition: a Charlottenburg row
    repeated under Steglitz in place of 06100102).
    """
    import pdfplumber  # build-time dependency only

    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    rows: dict[str, UgRow] = {}
    errata: list[str] = []
    section: str | None = None
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            anchors_by_text = {w["text"]: w["x0"] for w in words if w["text"] in UG_HEADERS}
            if len(anchors_by_text) != len(UG_HEADERS):
                continue  # not a table page
            anchors = [anchors_by_text[h] for h in UG_HEADERS]
            for line in _group_lines(words):
                texts = [w["text"] for w in line]
                if texts and texts[0] == "BEZIRK":
                    name = district_key(" ".join(texts[1:]))
                    if name not in district_codes:
                        raise BuildError(f"Unknown district heading {' '.join(texts)!r}")
                    section = district_codes[name]
                    continue
                if not texts or not re.fullmatch(r"\d{8}", texts[0]):
                    continue
                key = texts[0]
                runs = [(w["x0"], len(w["text"])) for w in line if set(w["text"]) == {"■"}]
                cells = decode_ug_row(runs, anchors)
                if section is None or key[:2] != section or key in rows:
                    errata.append(key)
                    continue
                rows[key] = UgRow(key, tuple(cells[1:5]))  # social column dropped here
    return rows, errata


# --- Bundle assembly ----------------------------------------------------------------

UG_MIN_COVERAGE = 0.5  # a region needs UG classes for >= 50% of its residents
UG_UNITS = {
    "quiet": "noise burden class, 1 low – 3 high",
    "clean_air": "air-pollution burden class, 1 low – 3 high",
    "cool_summer": "heat burden class, 1 low – 3 high",
    "green": "green-space supply class, 1 good – 3 poor",
}
UG_LABELS = {
    "quiet": "traffic noise (Strategische Lärmkarte 2022)",
    "clean_air": "NO₂/PM (2023 measurements)",
    "cool_summer": "day and night heat (Klimamodell 2022)",
    "green": "public green space per resident (Versorgungsanalyse 2020)",
}
UG_YEARS = {"quiet": "2022", "clean_air": "2023", "cool_summer": "2022", "green": "2020"}

# Access attributes from OSM / VBB (see access.py): unit, label, scale, source.
ACCESS_MEASURES = {
    "cafes": ("cafés, restaurants and bakeries within 500 m", "log", OSM),
    "everyday": ("supermarkets, pharmacies and doctors within 500 m", "log", OSM),
    "nightlife": ("bars, pubs, clubs and beer gardens within 1 km", "log", OSM),
    "culture": ("museums, theatres, cinemas, arts centres and libraries within 1.5 km", "log", OSM),
    "sport": ("gyms, pools and sports centres within 1 km", "log", OSM),
    "water": ("metres to the nearest lake/river/canal or forest", "linear", OSM),
    "transit": ("metres to the nearest S-/U-Bahn, regional-rail or tram stop", "linear", VBB),
}


def _is_region_key(key: str) -> bool:
    """A Bezirksregion (not a district total 'xx0000', 'unassignable' xx9900, or city)."""
    return not key.endswith("0000") and key[2:4] != "99" and key[:2] != "99"


def _percentile_reference(values: list[float], berlin: float, unit: str) -> dict:
    deciles = statistics.quantiles(values, n=10, method="inclusive")
    return {
        "low": round(deciles[0], 4),
        "high": round(deciles[8], 4),
        "berlin": berlin,
        "unit": unit,
        "method": "10th–90th percentile across Berlin's 143 regions",
    }


def _class_reference(berlin: float, unit: str) -> dict:
    return {
        "low": 1.0,
        "high": 3.0,
        "berlin": berlin,
        "unit": unit,
        "method": "class bounds: 1 = all residents in the best quarter of Berlin, "
        "3 = all in the worst quarter",
    }


def _weighted_classes(items: list[tuple[int, int]]) -> tuple[float, dict[str, float]]:
    """(population, class) pairs -> (population-weighted mean class, % per class)."""
    total = sum(p for p, _ in items)
    mean = sum(p * c for p, c in items) / total
    shares = {
        name: round(100 * sum(p for p, c in items if c == cls) / total, 1)
        for cls, name in UG_CLASS_NAMES.items()
    }
    return mean, shares


def _weighted(pairs: Iterable[tuple[float, float]]) -> float:
    """Weighted mean of (weight, value) pairs."""
    pairs = list(pairs)
    total = sum(w for w, _ in pairs)
    return sum(w * v for w, v in pairs) / total


def commute_matrix(regions: list[dict], network, reference: str) -> dict:
    """Public-transport minutes from every region's centre to every fixed destination.

    Uses the same estimator as listing commutes (enrich.commute, ADR-0009): a route over
    the VBB weekday-peak network, falling back to the straight-line estimate when no
    sensible route exists. Computed once here, so requests never route and never send
    a user's destination anywhere.
    """
    from enrich.commute import estimate_with_network

    times: dict[str, dict[str, dict]] = {}
    for dest in DESTINATIONS:
        times[dest["id"]] = {}
        for region in regions:
            lat, lng = region["centroid"]
            result = estimate_with_network(lat, lng, dest["lat"], dest["lng"], network)
            times[dest["id"]][region["key"]] = {
                "minutes": result.minutes,
                "changes": result.changes,
                "source": "network" if result.source == "network" else "distance",
            }
    return {
        "method": f"Door-to-door public transport from the region's resident-weighted centre, "
        f"routed over the VBB weekday-peak timetable ({reference}); walking to and from "
        "stops included. Straight-line estimate where no route is found.",
        "source_id": VBB,
        "times": times,
    }


def build_bundle(
    register_rows: list[PlanningAreaRow],
    crime: CrimeTable,
    planning_areas: dict[str, PlanningArea] | None = None,
    ug_rows: dict[str, UgRow] | None = None,
    access: dict[str, PlrAccess] | None = None,
    *,
    network=None,
    network_reference: str = "",
    inputs: dict[str, str] | None = None,
) -> dict:
    """Join everything on LOR keys and return the bundle dict (validated)."""
    plr_pop = {r.region_key + r.planungsraum: r.total for r in register_rows}

    # Aggregate Planungsräume -> Bezirksregionen.
    totals: dict[str, int] = {}
    ages: dict[str, list[int]] = {}
    for row in register_rows:
        totals[row.region_key] = totals.get(row.region_key, 0) + row.total
        acc = ages.setdefault(row.region_key, [0] * len(AGE_COLUMNS))
        for i, n in enumerate(row.ages):
            acc[i] += n

    crime_regions = {k for k in crime.kieztaten if _is_region_key(k)}
    if set(totals) != crime_regions:
        only_pop = sorted(set(totals) - crime_regions)
        only_crime = sorted(crime_regions - set(totals))
        raise BuildError(f"Join mismatch: register-only {only_pop}, crime-only {only_crime}")
    for key in crime_regions:
        missing = [y for y in CRIME_YEARS if y not in crime.kieztaten[key]]
        if missing:
            raise BuildError(f"{key}: no Kieztaten value for {missing}")
    if planning_areas is not None and set(planning_areas) != set(plr_pop):
        diff = sorted(set(planning_areas) ^ set(plr_pop))
        raise BuildError(f"LOR geometry and register disagree on Planungsräume: {diff[:10]}")

    plrs_by_region: dict[str, list[str]] = {}
    for plr_id in sorted(plr_pop):
        plrs_by_region.setdefault(plr_id[:6], []).append(plr_id)

    def district_of(key: str) -> str:
        return crime.names[key[:2] + "0000"]

    def kiez_mean(key: str) -> float:
        return statistics.fmean(crime.kieztaten[key][y] for y in CRIME_YEARS)

    years = f"{CRIME_YEARS[0]}–{CRIME_YEARS[-1]}"
    regions: list[dict] = []
    for key in sorted(totals):
        total = totals[key]
        a = dict(zip(AGE_COLUMNS, ages[key], strict=True))
        under_18 = a["u6"] + a["a6_15"] + a["a15_18"]
        region: dict = {
            "key": key,
            "name": region_meta.display_name(key, crime.names[key]),
            "district": district_of(key),
            "population": total,
            "listing_kiez": region_meta.LISTING_KIEZ.get(key),
            "centroid": None,
            "measures": {
                "safety": {
                    "raw": round(kiez_mean(key), 1),
                    "unit": "neighbourhood offences per 100,000 residents",
                    "source_id": PKS,
                    "year": years,
                    "method": f"Mean of the ‘Kieztaten’ Häufigkeitszahl {years}.",
                },
                "family": {
                    "raw": round(100 * under_18 / total, 2),
                    "unit": "% of residents under 18",
                    "source_id": REGISTER,
                    "year": "2024",
                    "method": "Residents aged 0–17 ÷ all residents, summed over the "
                    "region's Planungsräume.",
                },
                "young_crowd": {
                    "raw": round(100 * a["a18_27"] / total, 2),
                    "unit": "% of residents aged 18–27",
                    "source_id": REGISTER,
                    "year": "2024",
                    "method": "Residents aged 18–26 ÷ all residents, summed over the "
                    "region's Planungsräume.",
                },
            },
        }

        if planning_areas is not None:
            plrs = [planning_areas[p] for p in plrs_by_region[key]]
            area_m2 = sum(p.area_m2 for p in plrs)
            # Centre = resident-weighted mean of where people live in each PLR (OSM
            # residential land when available, else the PLR's area centroid).
            homes = [
                (
                    plr_pop[p.plr_id],
                    (access[p.plr_id].home_centroid if access and p.plr_id in access else None)
                    or p.centroid,
                )
                for p in plrs
                if plr_pop[p.plr_id] > 0
            ]
            lat = _weighted((w, c[0]) for w, c in homes)
            lng = _weighted((w, c[1]) for w, c in homes)
            has_shapes = all(p.polygons for p in plrs)
            if has_shapes and not any(geo.point_in_polygons(lng, lat, p.polygons) for p in plrs):
                # Concave region: the weighted centre lies outside it (e.g. Marzahn Süd).
                # Snap to the nearest real residential point inside the region.
                anchors = [
                    (access[p.plr_id].anchor if access and p.plr_id in access else None)
                    or p.centroid
                    for p in plrs
                    if plr_pop[p.plr_id] > 0
                ]
                lat, lng = min(anchors, key=lambda a: (a[0] - lat) ** 2 + (a[1] - lng) ** 2)
            inner_share = sum(plr_pop[p.plr_id] for p in plrs if p.inner_city) / total
            median, low, high = DISTRICT_RENTS[region["district"]]
            region.update(
                centroid=[round(lat, 5), round(lng, 5)],
                geo_source_id=LOR,
                area_km2=round(area_m2 / 1e6, 3),
                density_per_km2=round(total / (area_m2 / 1e6)),
                inner_city_share=round(inner_share, 3),
                rent_range=[low, high],
                rent={
                    "raw": median,
                    "unit": "EUR/m² net cold, median asking rent in the district",
                    "source_id": IBB_TABLES,
                    "year": "2025",
                    "method": f"District median for {region['district']} (IBB Tabellenband "
                    f"2025, Tab. 25); 80% of offers there were €{low:.2f}–{high:.2f}/m².",
                },
            )

        if access is not None:
            plr_values = [
                (plr_pop[p], access[p])
                for p in plrs_by_region[key]
                if p in access and plr_pop[p] > 0
            ]
            for attr, (unit, _scale, source_id) in ACCESS_MEASURES.items():
                raw = _weighted((w, a.values[attr]) for w, a in plr_values)
                method = (
                    "Resident-weighted mean over 100 m sample points on the region's "
                    "residential land (OSM), straight-line distance."
                )
                if attr == "water":
                    water_m = _weighted((w, a.water_m) for w, a in plr_values)
                    forest_m = _weighted((w, a.forest_m) for w, a in plr_values)
                    method += (
                        f" Nearest water ≥ 1 ha ≈ {water_m:,.0f} m, forest ≥ 5 ha ≈ "
                        f"{forest_m:,.0f} m (capped at 3 km)."
                    )
                region["measures"][attr] = {
                    "raw": round(raw, 1),
                    "unit": unit,
                    "source_id": source_id,
                    "year": "2026",
                    "method": method,
                }

        if ug_rows is not None:
            for i, attr in enumerate(UG_INDICATORS):
                items = [
                    (plr_pop[p], ug_rows[p].classes[i])
                    for p in plrs_by_region[key]
                    if p in ug_rows and ug_rows[p].classes[i] is not None and plr_pop[p] > 0
                ]
                covered = sum(pop for pop, _ in items)
                if covered < UG_MIN_COVERAGE * total:
                    continue  # not enough data: attribute stays unscored for this region
                mean, shares = _weighted_classes(items)
                region["measures"][attr] = {
                    "raw": round(mean, 3),
                    "unit": UG_UNITS[attr],
                    "source_id": UG_ATLAS,
                    "year": UG_YEARS[attr],
                    "method": f"Resident-weighted mean of the Planungsraum classes for "
                    f"{UG_LABELS[attr]}; covers {covered / total:.0%} of residents.",
                    "shares": shares,
                }
        regions.append(region)

    city_total = sum(totals.values())
    city_under_18 = sum(sum(ages[k][:3]) for k in ages)
    city_18_27 = sum(ages[k][3] for k in ages)

    def pct_ref(attr: str, berlin: float) -> dict:
        vals = [r["measures"][attr]["raw"] for r in regions]
        return _percentile_reference(vals, berlin, regions[0]["measures"][attr]["unit"])

    references = {
        "safety": pct_ref("safety", round(kiez_mean(CITY_KEY), 1)),
        "family": pct_ref("family", round(100 * city_under_18 / city_total, 2)),
        "young_crowd": pct_ref("young_crowd", round(100 * city_18_27 / city_total, 2)),
    }
    if ug_rows is not None:
        for i, attr in enumerate(UG_INDICATORS):
            items = [
                (plr_pop[p], row.classes[i])
                for p, row in ug_rows.items()
                if row.classes[i] is not None and plr_pop.get(p, 0) > 0
            ]
            mean, _ = _weighted_classes(items)
            references[attr] = _class_reference(round(mean, 3), UG_UNITS[attr])
    if access is not None:
        for attr, (_unit, scale, _source) in ACCESS_MEASURES.items():
            berlin = _weighted(
                (plr_pop[p], a.values[attr]) for p, a in access.items() if plr_pop.get(p, 0) > 0
            )
            references[attr] = {**pct_ref(attr, round(berlin, 1)), "scale": scale}

    bundle = {
        "schema_version": SCHEMA_VERSION,
        "inputs": dict(sorted((inputs or {}).items())),
        "sources": SOURCES,
        "city": CITY_FIGURES,
        "references": references,
        "regions": regions,
    }
    if network is not None and planning_areas is not None:
        bundle["destinations"] = DESTINATIONS
        bundle["commute"] = commute_matrix(regions, network, network_reference)
    ProfileBundle.model_validate(bundle)  # same validation the API applies on load
    return bundle


# --- Region outlines ----------------------------------------------------------------

SHAPE_TOLERANCE_M = 5.0


def region_shapes(planning_areas: dict[str, PlanningArea], bundle: dict) -> dict:
    """One simplified outline per Bezirksregion (GeoJSON), for the map and listing lookup.

    Planning areas are dissolved (shared borders cancel) and simplified with
    Douglas–Peucker at 5 m; area is preserved to within ~1%.
    """
    polygons: dict[str, list] = {}
    for area in planning_areas.values():
        polygons.setdefault(area.bzr_id, []).extend(area.polygons)
    names = {r["key"]: (r["name"], r["district"]) for r in bundle["regions"]}
    features = []
    for key in sorted(polygons):
        rings = [geo.simplify_ring(r, SHAPE_TOLERANCE_M) for r in geo.dissolve(polygons[key])]
        name, district = names[key]
        features.append(
            {
                "type": "Feature",
                "properties": {"key": key, "name": name, "district": district},
                "geometry": {"type": "MultiPolygon", "coordinates": geo.rings_to_polygons(rings)},
            }
        )
    return {
        "type": "FeatureCollection",
        "attribution": "LOR 2021 (SenStadt / Amt für Statistik Berlin-Brandenburg), simplified",
        "features": features,
    }


# --- CLI ----------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_one(raw_dir: Path, pattern: str) -> Path:
    matches = sorted(raw_dir.glob(pattern))
    if not matches:
        raise BuildError(f"No file matching {pattern!r} in {raw_dir} (see raw/README.md)")
    return matches[-1]  # latest edition if several


def compute_access_from_files(
    osm_zip: Path,
    network,  # data.vbb_network.Network
    planning_areas: dict[str, PlanningArea],
    register_rows: list[PlanningAreaRow],
) -> dict[str, PlrAccess]:
    """Unpack the OSM GeoPackage and measure access per PLR."""
    from data.lifestyle.access import compute_access, rapid_stops

    stops = rapid_stops(network.stations, network.rides)
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(osm_zip) as zf:
        gpkg_name = next(n for n in zf.namelist() if n.endswith(".gpkg"))
        gpkg = Path(zf.extract(gpkg_name, tmp))
        return compute_access(
            gpkg,
            {k: a.polygons for k, a in planning_areas.items()},
            {k: a.centroid for k, a in planning_areas.items()},
            {r.region_key + r.planungsraum: r.total for r in register_rows},
            stops,
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out", type=Path, default=BUNDLE_PATH)
    parser.add_argument("--shapes-out", type=Path, default=SHAPES_PATH)
    args = parser.parse_args(argv)

    crime_path = _find_one(args.raw_dir, CRIME_GLOB)
    register_path = _find_one(args.raw_dir, REGISTER_GLOB)
    lor_path = _find_one(args.raw_dir, LOR_GLOB)
    ug_path = _find_one(args.raw_dir, UG_GLOB)

    register_rows = read_register_pdf(register_path)
    crime = read_crime_xlsx(crime_path)
    planning_areas = read_lor_geojson(lor_path)
    district_codes = {
        district_key(name): key[:2] for key, name in crime.names.items() if key.endswith("0000")
    }
    ug_rows, errata = read_ug_pdf(ug_path, district_codes)
    missing_ug = sorted(set(planning_areas) - set(ug_rows))

    osm_zip = _find_one(args.raw_dir, OSM_GLOB)
    gtfs_zip = _find_one(args.raw_dir, GTFS_GLOB)
    from data.vbb_network import extract_network
    from enrich.transit_network import network_from_records

    extracted = extract_network(gtfs_zip)
    access = compute_access_from_files(osm_zip, extracted, planning_areas, register_rows)
    router = network_from_records(
        (
            {"station_id": sid, "name": n, "lat": lat, "lng": lng}
            for sid, (n, lat, lng) in extracted.stations.items()
        ),
        extracted.rides,
        extracted.boardings,
    )
    meta = extracted.meta
    reference = f"{meta['weekday']} {meta['reference_date']}, {meta['peak_window']}"

    bundle = build_bundle(
        register_rows,
        crime,
        planning_areas,
        ug_rows,
        access,
        network=router,
        network_reference=reference,
        inputs={
            p.name: _sha256(p)
            for p in (crime_path, register_path, lor_path, ug_path, osm_zip, gtfs_zip)
        },
    )
    args.out.write_text(json.dumps(bundle, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    shapes = region_shapes(planning_areas, bundle)
    args.shapes_out.write_text(
        json.dumps(shapes, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    population = sum(r["population"] for r in bundle["regions"])
    print(
        f"Wrote {args.out} — {len(bundle['regions'])} regions, "
        f"{len(register_rows)} Planungsräume, {population:,} residents."
    )
    print(
        f"  Umweltgerechtigkeit: {len(ug_rows)} Planungsräume parsed; "
        f"errata skipped {errata}; no data for {missing_ug}"
    )
    straight = sum(
        t["source"] == "distance" for d in bundle["commute"]["times"].values() for t in d.values()
    )
    print(
        f"  Commute: {len(bundle['destinations'])} destinations × {len(bundle['regions'])} "
        f"regions ({reference}); straight-line fallback for {straight}"
    )
    fallback = sorted(k for k, a in access.items() if a.samples == 0)
    print(f"  Access: {len(access)} Planungsräume measured; centroid fallback for {fallback}")
    for attr, ref in bundle["references"].items():
        print(f"  {attr:12} low={ref['low']:>9} high={ref['high']:>9} Berlin={ref['berlin']}")


if __name__ == "__main__":
    main()
