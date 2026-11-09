"""Walking-distance access measured from where people live (OSM + VBB).

Method, per LOR-Planungsraum (PLR):

1. **Resident sample points.** A 100 m grid laid over OSM `landuse=residential`
   polygons; each grid point is assigned to the PLR containing it. A PLR's registered
   residents are spread evenly over its points, so a region's figure describes the
   typical resident's doorstep — not the middle of a forest or a rail yard. PLRs with
   residents but no mapped residential land fall back to their area centroid.
2. **Amenities within walking radius** (OSM POIs; see osm.AMENITY_CATEGORIES): the mean
   number reachable in a straight line from the sample points.
3. **Nearest water or forest**: distance to the edge of a lake/river/canal ≥ 1 ha or a
   forest ≥ 5 ha (edges densified to 50 m), capped at 3 km.
4. **Nearest rapid transit**: distance to the nearest S-Bahn, U-Bahn, regional-rail or
   tram stop with service in the VBB weekday-peak network (ADR-0009), capped at 3 km.

The build then weights PLR values by residents up to Bezirksregionen.
Straight-line distances understate real walking routes a little; the caveat says so.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from data.lifestyle import geo
from data.lifestyle.osm import (
    AMENITY_CATEGORIES,
    FOREST_MIN_M2,
    WATER_CLASSES,
    WATER_MIN_M2,
    read_layer,
)

GRID_STEP_M = 100.0
EDGE_STEP_M = 50.0
DISTANCE_CAP_M = 3000.0
RAPID_ROUTE_TYPES = frozenset({"100", "106", "109", "400", "900"})  # rail, S, U, tram

POI_LAYERS = ("gis_osm_pois_free", "gis_osm_pois_a_free")


@dataclass(frozen=True)
class PlrAccess:
    samples: int  # resident sample points used (0 = centroid fallback)
    values: dict[str, float]  # attribute -> mean count / distance (m)
    water_m: float  # components of `water`, for the explanation
    forest_m: float
    home_centroid: tuple[float, float] | None  # (lat, lng) mean of sample points
    # A real residential sample point (the one nearest the mean), guaranteed inside the
    # PLR — used when a region's weighted centre falls outside an oddly shaped region.
    anchor: tuple[float, float] | None = None


class _PolygonLookup:
    """Which PLR contains a point (1 km cell -> candidate PLRs -> point-in-polygon)."""

    def __init__(self, polygons: Mapping[str, list[geo.Polygon]]) -> None:
        self.polygons = polygons
        self.cells: dict[tuple[int, int], list[str]] = {}
        for key, polys in polygons.items():
            min_lng, min_lat, max_lng, max_lat = geo.bbox(polys)
            x0, y0 = geo.to_xy(min_lng, min_lat)
            x1, y1 = geo.to_xy(max_lng, max_lat)
            for i in range(int(x0 // 1000), int(x1 // 1000) + 1):
                for j in range(int(y0 // 1000), int(y1 // 1000) + 1):
                    self.cells.setdefault((i, j), []).append(key)

    def find(self, x: float, y: float) -> str | None:
        lng, lat = geo.to_lnglat(x, y)
        for key in self.cells.get((int(x // 1000), int(y // 1000)), ()):
            if geo.point_in_polygons(lng, lat, self.polygons[key]):
                return key
        return None


def grid_points_in(polygon: geo.Polygon, step: float = GRID_STEP_M) -> list[tuple[float, float]]:
    """Grid points (x, y metres; multiples of `step`) inside one polygon."""
    min_lng, min_lat, max_lng, max_lat = geo.bbox([polygon])
    x0, y0 = geo.to_xy(min_lng, min_lat)
    x1, y1 = geo.to_xy(max_lng, max_lat)
    points = []
    gx = math.ceil(x0 / step) * step
    while gx <= x1:
        gy = math.ceil(y0 / step) * step
        while gy <= y1:
            lng, lat = geo.to_lnglat(gx, gy)
            if geo.point_in_polygons(lng, lat, [polygon]):
                points.append((round(gx, 3), round(gy, 3)))
            gy += step
        gx += step
    return points


def resident_samples(
    residential: Iterable[geo.Polygon], plr_polygons: Mapping[str, list[geo.Polygon]]
) -> dict[str, list[tuple[float, float]]]:
    """PLR -> grid points on residential land inside it (deduplicated, sorted)."""
    points: set[tuple[float, float]] = set()
    for polygon in residential:
        points.update(grid_points_in(polygon))
    lookup = _PolygonLookup(plr_polygons)
    by_plr: dict[str, list[tuple[float, float]]] = {}
    for x, y in sorted(points):
        key = lookup.find(x, y)
        if key is not None:
            by_plr.setdefault(key, []).append((x, y))
    return by_plr


def amenity_index(features: Iterable[tuple[str, float, float]]) -> dict[str, geo.GridIndex]:
    """(fclass, lng, lat) -> one grid index per amenity attribute."""
    indexes = {attr: geo.GridIndex(radius) for attr, (_, radius) in AMENITY_CATEGORIES.items()}
    for fclass, lng, lat in features:
        x, y = geo.to_xy(lng, lat)
        for attr, (classes, _) in AMENITY_CATEGORIES.items():
            if fclass in classes:
                indexes[attr].add(x, y, attr)
    return indexes


def edge_index(polygons: Iterable[geo.Polygon], min_area_m2: float) -> geo.GridIndex:
    """Densified outer edges of polygons at least `min_area_m2` large."""
    index = geo.GridIndex(500)
    for polygon in polygons:
        area, _, _ = geo.ring_area_centroid(polygon[0])
        if area >= min_area_m2:
            for x, y in geo.densify_ring(polygon[0], EDGE_STEP_M):
                index.add(x, y)
    return index


def point_index(points: Iterable[tuple[float, float]]) -> geo.GridIndex:
    index = geo.GridIndex(500)
    for lng, lat in points:
        index.add(*geo.to_xy(lng, lat))
    return index


def measure_plr(
    points: list[tuple[float, float]],
    amenities: Mapping[str, geo.GridIndex],
    water: geo.GridIndex,
    forest: geo.GridIndex,
    transit: geo.GridIndex,
) -> tuple[dict[str, float], float, float]:
    """Mean access over sample points: amenity counts, nature and transit distances."""
    totals = dict.fromkeys(AMENITY_CATEGORIES, 0.0)
    water_sum = forest_sum = nature_sum = transit_sum = 0.0
    for x, y in points:
        for attr, (_, radius) in AMENITY_CATEGORIES.items():
            totals[attr] += amenities[attr].count_within(x, y, radius).get(attr, 0)
        w = water.nearest(x, y, DISTANCE_CAP_M)
        f = forest.nearest(x, y, DISTANCE_CAP_M)
        water_sum += w
        forest_sum += f
        nature_sum += min(w, f)
        transit_sum += transit.nearest(x, y, DISTANCE_CAP_M)
    n = len(points)
    values = {attr: total / n for attr, total in totals.items()}
    values["water"] = nature_sum / n
    values["transit"] = transit_sum / n
    return values, water_sum / n, forest_sum / n


def compute_access(
    gpkg: Path,
    plr_polygons: Mapping[str, list[geo.Polygon]],
    plr_centroids: Mapping[str, tuple[float, float]],  # (lat, lng)
    plr_population: Mapping[str, int],
    rapid_stops: Iterable[tuple[float, float]],  # (lng, lat)
) -> dict[str, PlrAccess]:
    """Access values for every PLR with residents."""
    residential = [
        p
        for f in read_layer(gpkg, "gis_osm_landuse_a_free", frozenset({"residential"}))
        for p in f.polygons or []
    ]
    samples = resident_samples(residential, plr_polygons)

    classes = frozenset().union(*(c for c, _ in AMENITY_CATEGORIES.values()))
    pois: list[tuple[str, float, float]] = []
    for layer in POI_LAYERS:
        for f in read_layer(gpkg, layer, classes):
            if f.point is not None:
                lng, lat = f.point
            else:
                _, (lat, lng) = geo.polygons_area_centroid(f.polygons or [])
            pois.append((f.fclass, lng, lat))
    amenities = amenity_index(pois)

    water = edge_index(
        (
            p
            for f in read_layer(gpkg, "gis_osm_water_a_free", WATER_CLASSES)
            for p in f.polygons or []
        ),
        WATER_MIN_M2,
    )
    forest = edge_index(
        (
            p
            for f in read_layer(gpkg, "gis_osm_landuse_a_free", frozenset({"forest"}))
            for p in f.polygons or []
        ),
        FOREST_MIN_M2,
    )
    transit = point_index(rapid_stops)

    result: dict[str, PlrAccess] = {}
    for key in sorted(plr_polygons):
        if plr_population.get(key, 0) <= 0:
            continue
        points = samples.get(key)
        used = len(points) if points else 0
        if not points:  # residents but no mapped residential land: use the centroid
            lat, lng = plr_centroids[key]
            points = [geo.to_xy(lng, lat)]
        values, water_m, forest_m = measure_plr(points, amenities, water, forest, transit)
        home = anchor = None
        if used:
            mx, my = sum(x for x, _ in points) / used, sum(y for _, y in points) / used
            lng, lat = geo.to_lnglat(mx, my)
            home = (lat, lng)
            ax, ay = min(points, key=lambda p: (p[0] - mx) ** 2 + (p[1] - my) ** 2)
            a_lng, a_lat = geo.to_lnglat(ax, ay)
            anchor = (a_lat, a_lng)
        result[key] = PlrAccess(used, values, water_m, forest_m, home, anchor)
    return result


def rapid_stops(stations: Mapping[str, tuple[str, float, float]], rides: Iterable[dict]) -> list:
    """(lng, lat) of stations served by rail/S/U/tram in the peak network (vbb_network)."""
    served = set()
    for ride in rides:
        if ride["route_type"] in RAPID_ROUTE_TYPES:
            served.update((ride["from_station"], ride["to_station"]))
    return sorted((stations[s][2], stations[s][1]) for s in served if s in stations)
