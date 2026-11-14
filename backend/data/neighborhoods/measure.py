"""Spatial measurements per Bezirksregion for Berlin Neighbourhoods (build time only).

Two kinds of figures:

1. **From the doorstep** (same method as Lifestyle Match, ADR-0010): a 100 m grid over
   OSM residential land gives "home" sample points in each region; we average, over
   those homes, how many facilities lie within walking radius and how far the nearest
   hospital or park is. Figures describe where people live, not parks or rail yards.
   Unlike Lifestyle Match (which spreads each Planungsraum's residents over its points),
   every home point in a region counts equally here; the Planungsraum register isn't an
   input of this build.
2. **Inside the region**: injury road accidents (Unfallatlas) and the length of the
   public street network, counted by point-in-polygon against the region outlines.

Which OSM feature classes count for what is defined once, in `FACILITIES`, so the
method text shown to users and the code can't drift.
"""

from __future__ import annotations

import math
import sqlite3
import statistics
import struct
from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from data.lifestyle import geo
from data.lifestyle.access import _PolygonLookup, edge_index, resident_samples
from data.lifestyle.osm import _wkb_offset, read_layer

POI_LAYERS = ("gis_osm_pois_free", "gis_osm_pois_a_free")


@dataclass(frozen=True)
class Facility:
    """Facilities counted within walking radius of homes."""

    layers: tuple[str, ...]
    fclasses: frozenset[str]
    radius_m: int
    label: str  # plural noun phrase for the unit text


FACILITIES: dict[str, Facility] = {
    "doctors": Facility(
        POI_LAYERS,
        frozenset({"doctors", "dentist", "clinic"}),
        1000,
        "doctors, dentists and clinics",
    ),
    "pharmacies": Facility(POI_LAYERS, frozenset({"pharmacy"}), 500, "pharmacies"),
    "schools": Facility(POI_LAYERS, frozenset({"school"}), 1000, "schools"),
    "kitas": Facility(POI_LAYERS, frozenset({"kindergarten"}), 500, "Kitas (day-care centres)"),
    "playgrounds": Facility(POI_LAYERS, frozenset({"playground"}), 500, "playgrounds"),
    "stops": Facility(
        ("gis_osm_transport_free", "gis_osm_transport_a_free"),
        frozenset({"bus_stop", "tram_stop", "railway_station", "railway_halt"}),
        500,
        "bus, tram and rail stops",
    ),
}

HOSPITAL_CLASSES = frozenset({"hospital"})
HOSPITAL_CAP_M = 15_000.0
PARK_MIN_M2 = 10_000  # ≥ 1 ha: a real park, not a green strip
PARK_CAP_M = 3_000.0
PARKING_METER_RADIUS_M = 150  # a ticket machine this close → the street has paid parking
PARKING_AREA_RADIUS_M = 300

# Public streets for "accidents per km of street": everything cars and bikes share,
# not footways, paths, tracks or private service roads.
STREET_CLASSES = frozenset(
    {
        "motorway",
        "motorway_link",
        "trunk",
        "trunk_link",
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
        "tertiary",
        "tertiary_link",
        "unclassified",
        "residential",
        "living_street",
    }
)


@dataclass
class RegionAccess:
    homes: int  # sample points used (0 = centroid fallback)
    counts: dict[str, float]  # facility id -> mean count within its radius
    hospital_m: float
    park_m: float
    paid_parking_share: float  # % of homes within PARKING_METER_RADIUS_M of a ticket machine
    parking_area_m2: float  # mean mapped car-parking area within PARKING_AREA_RADIUS_M


@dataclass
class RegionRoads:
    street_km: float = 0.0
    accidents: int = 0
    severe: int = 0  # killed or seriously injured
    vulnerable: int = 0  # a pedestrian or cyclist involved
    extra: dict = field(default_factory=dict)


# --- Geometry readers ------------------------------------------------------------------------


def read_lines(gpkg: Path, layer: str, fclasses: frozenset[str]) -> Iterable[list[tuple]]:
    """(lng, lat) vertex lists of LINESTRING features (GeoPackage WKB, types 2 / 1002…)."""
    con = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(fclasses))
        query = f'SELECT geom FROM "{layer}" WHERE fclass IN ({marks})'
        for (blob,) in con.execute(query, tuple(sorted(fclasses))):
            if blob is None:
                continue
            pos = _wkb_offset(blob)
            order = "<" if blob[pos] == 1 else ">"
            (gtype,) = struct.unpack_from(order + "I", blob, pos + 1)
            if gtype % 1000 != 2:
                continue
            dims = 2 + (gtype // 1000 in (1, 2)) + (gtype // 1000 == 3) * 2
            (n,) = struct.unpack_from(order + "I", blob, pos + 5)
            flat = struct.unpack_from(order + "d" * (n * dims), blob, pos + 9)
            yield [(flat[i], flat[i + 1]) for i in range(0, len(flat), dims)]
    finally:
        con.close()


def _points(gpkg: Path, layers: Iterable[str], fclasses: frozenset[str]) -> list[tuple]:
    """(lng, lat) of point features and of polygon features' centroids."""
    out = []
    for layer in layers:
        for f in read_layer(gpkg, layer, fclasses):
            if f.point is not None:
                out.append(f.point)
            else:
                _, (lat, lng) = geo.polygons_area_centroid(f.polygons or [])
                out.append((lng, lat))
    return out


class WeightedGrid:
    """Grid index of points carrying a weight (e.g. a car park's area)."""

    def __init__(self, cell_m: float) -> None:
        self.cell = cell_m
        self.cells: dict[tuple[int, int], list[tuple[float, float, float]]] = {}

    def add(self, x: float, y: float, w: float) -> None:
        self.cells.setdefault((int(x // self.cell), int(y // self.cell)), []).append((x, y, w))

    def sum_within(self, x: float, y: float, radius: float) -> float:
        r = math.ceil(radius / self.cell)
        cx, cy = int(x // self.cell), int(y // self.cell)
        r2, total = radius * radius, 0.0
        for i in range(cx - r, cx + r + 1):
            for j in range(cy - r, cy + r + 1):
                for px, py, w in self.cells.get((i, j), ()):
                    if (px - x) ** 2 + (py - y) ** 2 <= r2:
                        total += w
        return total


# --- Pure measurement (unit-tested with synthetic points) ------------------------------------


def measure_homes(
    homes: list[tuple[float, float]],
    facilities: Mapping[str, geo.GridIndex],
    hospitals: geo.GridIndex,
    parks: geo.GridIndex,
    meters: geo.GridIndex,
    parking: WeightedGrid,
) -> RegionAccess:
    """Means over a region's home points (x, y metres)."""
    totals = dict.fromkeys(FACILITIES, 0.0)
    hospital = park = paid = area = 0.0
    for x, y in homes:
        for fid, fac in FACILITIES.items():
            totals[fid] += facilities[fid].count_within(x, y, fac.radius_m).get(fid, 0)
        hospital += hospitals.nearest(x, y, HOSPITAL_CAP_M)
        park += parks.nearest(x, y, PARK_CAP_M)
        paid += meters.nearest(x, y, PARKING_METER_RADIUS_M + 1) <= PARKING_METER_RADIUS_M
        area += parking.sum_within(x, y, PARKING_AREA_RADIUS_M)
    n = len(homes)
    return RegionAccess(
        homes=n,
        counts={fid: t / n for fid, t in totals.items()},
        hospital_m=hospital / n,
        park_m=park / n,
        paid_parking_share=100 * paid / n,
        parking_area_m2=area / n,
    )


def assign_accidents(accidents: Iterable, lookup) -> dict[str, RegionRoads]:
    """Count accidents per region (`lookup.find(x, y)` → region key or None)."""
    out: dict[str, RegionRoads] = {}
    for a in accidents:
        key = lookup.find(*geo.to_xy(a.lng, a.lat))
        if key is None:
            continue
        r = out.setdefault(key, RegionRoads())
        r.accidents += 1
        r.severe += a.severe
        r.vulnerable += a.bike or a.pedestrian
    return out


def street_km_by_region(lines: Iterable[list[tuple]], lookup) -> dict[str, float]:
    """Street length per region; each segment counts where its midpoint lies.

    Lookups are memoised on a 25 m grid of midpoints (streets share cells), which keeps
    this to a few seconds for Berlin's ~90,000 street ways.
    """
    cache: dict[tuple[int, int], str | None] = {}
    out: dict[str, float] = {}
    for line in lines:
        pts = [geo.to_xy(lng, lat) for lng, lat in line]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            cell = (int(mx // 25), int(my // 25))
            if cell not in cache:
                cache[cell] = lookup.find(mx, my)
            key = cache[cell]
            if key is not None:
                out[key] = out.get(key, 0.0) + math.hypot(x2 - x1, y2 - y1) / 1000
    return out


# --- From the GeoPackage ------------------------------------------------------------------------


def home_samples(
    gpkg: Path, region_polygons: Mapping[str, list[geo.Polygon]]
) -> dict[str, list[tuple[float, float]]]:
    """Region -> home sample points (x, y metres): 100 m grid on OSM residential land."""
    residential = [
        p
        for f in read_layer(gpkg, "gis_osm_landuse_a_free", frozenset({"residential"}))
        for p in f.polygons or []
    ]
    return resident_samples(residential, region_polygons)


def measure_access(
    gpkg: Path,
    region_polygons: Mapping[str, list[geo.Polygon]],
    fallback_points: Mapping[str, tuple[float, float]],  # key -> (lat, lng)
    samples: Mapping[str, list[tuple[float, float]]] | None = None,
) -> dict[str, RegionAccess]:
    if samples is None:
        samples = home_samples(gpkg, region_polygons)

    facilities: dict[str, geo.GridIndex] = {}
    for fid, fac in FACILITIES.items():
        index = geo.GridIndex(fac.radius_m)
        for lng, lat in _points(gpkg, fac.layers, fac.fclasses):
            index.add(*geo.to_xy(lng, lat), fid)
        facilities[fid] = index

    hospitals = geo.GridIndex(3000)
    for lng, lat in _points(gpkg, POI_LAYERS, HOSPITAL_CLASSES):
        hospitals.add(*geo.to_xy(lng, lat))

    parks = edge_index(
        (
            p
            for f in read_layer(gpkg, "gis_osm_landuse_a_free", frozenset({"park"}))
            for p in f.polygons or []
        ),
        PARK_MIN_M2,
    )

    meters = geo.GridIndex(200)
    for lng, lat in _points(gpkg, ("gis_osm_pois_free",), frozenset({"vending_parking"})):
        meters.add(*geo.to_xy(lng, lat))

    parking = WeightedGrid(300)
    for f in read_layer(gpkg, "gis_osm_traffic_a_free", frozenset({"parking"})):
        area, (lat, lng) = _area_centroid(f.polygons or [])
        if area > 0:
            parking.add(*geo.to_xy(lng, lat), area)

    out: dict[str, RegionAccess] = {}
    for key in sorted(region_polygons):
        homes = samples.get(key)
        if homes:
            out[key] = measure_homes(homes, facilities, hospitals, parks, meters, parking)
        else:  # no mapped residential land: the region's centre point stands in
            lat, lng = fallback_points[key]
            r = measure_homes([geo.to_xy(lng, lat)], facilities, hospitals, parks, meters, parking)
            r.homes = 0
            out[key] = r
    return out


def _area_centroid(polygons: list) -> tuple[float, tuple[float, float]]:
    try:
        return geo.polygons_area_centroid(polygons)
    except ValueError:  # degenerate outline in OSM
        return 0.0, (0.0, 0.0)


def measure_roads(
    gpkg: Path, region_polygons: Mapping[str, list[geo.Polygon]], accidents: Iterable
) -> dict[str, RegionRoads]:
    lookup = _PolygonLookup(region_polygons)
    roads = assign_accidents(accidents, lookup)
    km = street_km_by_region(read_lines(gpkg, "gis_osm_roads_free", STREET_CLASSES), lookup)
    for key in region_polygons:
        roads.setdefault(key, RegionRoads()).street_km = km.get(key, 0.0)
    return roads


# --- Land values at homes (Bodenrichtwerte) ------------------------------------------------------


@dataclass(frozen=True)
class RegionLandValue:
    index: float  # 0–100: mean percentile of the homes' zones within their density class
    median_eur: float  # median Bodenrichtwert (EUR/m² of plot) over the homes
    homes: int  # home points inside a residential zone
    homes_total: int
    houses_share: float  # % of those homes in zones for houses (vs. blocks of flats)


def class_percentile(sorted_values: list[float], value: float) -> float:
    """0–100: share of Berlin's zones of the same class with a lower value (ties half)."""
    lo, hi = bisect_left(sorted_values, value), bisect_right(sorted_values, value)
    return 100 * (lo + (hi - lo) / 2) / len(sorted_values)


def land_values(
    samples: Mapping[str, list[tuple[float, float]]], zones: list
) -> dict[str, RegionLandValue]:
    """Per region: where its homes' land values stand among Berlin's residential zones.

    Each home point takes the Bodenrichtwert of the residential zone it lies in and is
    compared only with zones of the same density class (houses vs. flats — the
    Gutachterausschuss doesn't convert between them). The region's index is the mean
    of those percentiles. Homes outside any residential zone (e.g. in a commercial zone)
    are skipped; regions where none fall inside are left out.
    """
    by_class: dict[str, list[float]] = {}
    for z in zones:
        by_class.setdefault(z.density, []).append(z.value)
    for values in by_class.values():
        values.sort()
    lookup = _PolygonLookup({z.zone_id: z.polygons for z in zones})
    zone_by_id = {z.zone_id: z for z in zones}

    out: dict[str, RegionLandValue] = {}
    for key, points in samples.items():
        found = [zone_by_id[zid] for x, y in points if (zid := lookup.find(x, y)) is not None]
        if not found:
            continue
        pct = [class_percentile(by_class[z.density], z.value) for z in found]
        values = sorted(z.value for z in found)
        out[key] = RegionLandValue(
            index=sum(pct) / len(pct),
            median_eur=statistics.median(values),
            homes=len(found),
            homes_total=len(points),
            houses_share=100 * sum(z.density == "houses" for z in found) / len(found),
        )
    return out
