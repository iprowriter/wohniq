"""In-memory `BerlinData` over the build files (offline demo mode, and the build itself).

Everything is NumPy over small arrays except addresses (400,505 rows), which keep a sorted
search-key list for prefix search and a latitude-sorted index for nearest-address lookups.
"""

from __future__ import annotations

import bisect
import math
import sys
from pathlib import Path

import numpy as np

from berlin import files
from berlin.geo import (
    degree_box,
    haversine_m,
    local_xy,
    point_segment_distance,
    points_in_polygons,
)
from berlin.repository import POINT_LAYERS, Address, AirStation, Area, Park, Stop
from berlin.text import search_key


def _intern(cache: dict[str, str], value: str) -> str:
    return cache.setdefault(value, sys.intern(value))


class _PointLayer:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.lat = np.array([r["lat"] for r in rows], dtype=float)
        self.lng = np.array([r["lng"] for r in rows], dtype=float)

    def within(self, lat: float, lng: float, radius_m: float) -> list[dict]:
        if not self.rows:
            return []
        dlat, dlng = degree_box(lat, radius_m)
        box = np.nonzero((np.abs(self.lat - lat) <= dlat) & (np.abs(self.lng - lng) <= dlng))[0]
        if box.size == 0:
            return []
        d = haversine_m(lat, lng, self.lat[box], self.lng[box])
        keep = d <= radius_m
        order = np.argsort(d[keep], kind="stable")
        idx, dist = box[keep][order], d[keep][order]
        return [{**self.rows[i], "distance_m": float(dd)} for i, dd in zip(idx, dist, strict=True)]


class LocalBerlinData:
    def __init__(self, build_dir: Path | None = None, with_area_stats: bool = True):
        self.build_dir = build_dir or files.BUILD_DIR
        d = self.build_dir
        self._manifest = files.read_json(files.MANIFEST, d) if with_area_stats else {}
        rent = files.read_json(files.RENT_TABLE, d)
        self._periods, self._rent_rows = rent["periods"], rent["rows"]
        self._checklist = files.read_json(files.CHECKLIST, d)

        areas = files.read_json(files.AREAS, d)
        self.planning_areas: list[dict] = areas["planning_areas"]
        self._regions = {r["id"]: r for r in areas["district_regions"]}
        self._berlin_crime = float(areas["crime"]["berlin_rate"])
        self._plr_index = {a["id"]: a for a in self.planning_areas}
        self._plr_rings = [
            [[np.asarray(r, dtype=float) for r in poly] for poly in a["polygons"]]
            for a in self.planning_areas
        ]
        self._plr_bbox = np.array(
            [
                (
                    min(p[0] for poly in a["polygons"] for p in poly[0]),
                    min(p[1] for poly in a["polygons"] for p in poly[0]),
                    max(p[0] for poly in a["polygons"] for p in poly[0]),
                    max(p[1] for poly in a["polygons"] for p in poly[0]),
                )
                for a in self.planning_areas
            ]
        )
        self._area_stats = files.read_json(files.AREA_STATS, d)["areas"] if with_area_stats else {}

        stops = files.read_json(files.STOPS, d)
        self._stops = _PointLayer(stops)
        self._stop_modes = [frozenset(s["modes"]) for s in stops]
        self._layers = {
            "schools": _PointLayer(files.read_json(files.SCHOOLS, d)),
            "kitas": _PointLayer(files.read_json(files.KITAS, d)),
            "playgrounds": _PointLayer(files.read_json(files.PLAYGROUNDS, d)),
            "accidents": _PointLayer(
                [
                    {
                        "lat": float(r["lat"]),
                        "lng": float(r["lng"]),
                        "category": int(r["category"]),
                        "bike": r["bike"] == "1",
                        "pedestrian": r["pedestrian"] == "1",
                    }
                    for r in files.read_csv_gz(files.ACCIDENTS, d)
                ]
            ),
        }
        air = files.read_json(files.AIR, d)
        self._air = _PointLayer(air["stations"])
        self._load_parks(files.read_json(files.PARKS, d))
        self._load_addresses()

    # --- loading ------------------------------------------------------------------------

    def _load_parks(self, parks: list[dict]) -> None:
        self._parks = parks
        self._park_rings = [
            [[np.asarray(r, dtype=float) for r in poly] for poly in p["polygons"]] for p in parks
        ]
        self._park_bbox = np.array(
            [
                (
                    min(pt[0] for poly in p["polygons"] for pt in poly[0]),
                    min(pt[1] for poly in p["polygons"] for pt in poly[0]),
                    max(pt[0] for poly in p["polygons"] for pt in poly[0]),
                    max(pt[1] for poly in p["polygons"] for pt in poly[0]),
                )
                for p in parks
            ]
        )

    def _load_addresses(self) -> None:
        cache: dict[str, str] = {}
        ids, keys, rows = [], [], []
        lats, lngs, plrs = [], [], []
        for r in files.read_csv_gz(files.ADDRESSES, self.build_dir):
            ids.append(int(r["id"]))
            keys.append(r["search_key"])
            lat, lng = float(r["lat"]), float(r["lng"])
            lats.append(lat)
            lngs.append(lng)
            plr = _intern(cache, r["plr_id"])
            plrs.append(plr)
            rows.append(
                (
                    _intern(cache, r["street"]),
                    r["house_number"],
                    _intern(cache, r["postcode"]),
                    _intern(cache, r["district"]),
                    _intern(cache, r["location_class"]),
                    r["east"] == "1",
                    plr,
                )
            )
        if ids != list(range(1, len(ids) + 1)):
            raise files.BuildMissing("addresses file is not numbered 1…n in key order; rebuild")
        self._addr_keys = keys
        self._addr_rows = rows
        self.addr_lat = np.array(lats)
        self.addr_lng = np.array(lngs)
        self.addr_plr = plrs
        self._addr_by_lat = np.argsort(self.addr_lat, kind="stable")
        self._addr_lat_sorted = self.addr_lat[self._addr_by_lat]

    def _address(self, i: int) -> Address:
        street, hnr, plz, district, cls, east, plr = self._addr_rows[i]
        return Address(
            i + 1,
            street,
            hnr,
            plz,
            district,
            cls,
            east,
            plr,
            float(self.addr_lat[i]),
            float(self.addr_lng[i]),
        )

    # --- addresses ----------------------------------------------------------------------

    def search_addresses(self, query: str, limit: int = 10) -> list[Address]:
        prefix = search_key(query)
        if len(prefix) < 2:
            return []
        out = []
        i = bisect.bisect_left(self._addr_keys, prefix)
        while i < len(self._addr_keys) and len(out) < limit:
            if not self._addr_keys[i].startswith(prefix):
                break
            out.append(self._address(i))
            i += 1
        return out

    def address(self, address_id: int) -> Address | None:
        i = address_id - 1
        return self._address(i) if 0 <= i < len(self._addr_rows) else None

    def _addresses_near(
        self, lat: float, lng: float, radius_m: float
    ) -> tuple[np.ndarray, np.ndarray]:
        dlat, dlng = degree_box(lat, radius_m)
        lo = np.searchsorted(self._addr_lat_sorted, lat - dlat, "left")
        hi = np.searchsorted(self._addr_lat_sorted, lat + dlat, "right")
        cand = self._addr_by_lat[lo:hi]
        cand = cand[np.abs(self.addr_lng[cand] - lng) <= dlng]
        d = haversine_m(lat, lng, self.addr_lat[cand], self.addr_lng[cand])
        keep = d <= radius_m
        return cand[keep], d[keep]

    def nearest_address(
        self, lat: float, lng: float, district: str | None = None
    ) -> Address | None:
        radius = 100.0
        while radius <= 20_000:
            idx, d = self._addresses_near(lat, lng, radius)
            if district is not None and idx.size:
                mask = np.array([self._addr_rows[i][3] == district for i in idx], dtype=bool)
                idx, d = idx[mask], d[mask]
            if idx.size:
                # Ties (same point, several numbers) resolve to the lowest id, like ORDER BY.
                best = min(zip(d.tolist(), idx.tolist(), strict=True))
                return self._address(best[1])
            radius *= 2
        return None

    def location_class_share(self, lat: float, lng: float, radius_m: float) -> dict[str, float]:
        idx, _ = self._addresses_near(lat, lng, radius_m)
        if idx.size == 0:
            return {}
        counts: dict[str, int] = {}
        for i in idx:
            cls = self._addr_rows[i][4]
            counts[cls] = counts.get(cls, 0) + 1
        return {k: v / idx.size for k, v in counts.items()}

    # --- areas --------------------------------------------------------------------------

    def area_at(self, lat: float, lng: float) -> Area | None:
        b = self._plr_bbox
        cand = np.nonzero(
            (b[:, 0] <= lng) & (b[:, 2] >= lng) & (b[:, 1] <= lat) & (b[:, 3] >= lat)
        )[0]
        xs, ys = np.array([lng]), np.array([lat])
        for i in cand:
            if points_in_polygons(xs, ys, self._plr_rings[i])[0]:
                a = self.planning_areas[i]
                return Area(a["id"], a["name"], a["bzr_id"], a["bzr_name"], a["district"])
        return None

    def crime(self, bzr_id: str) -> float | None:
        r = self._regions.get(bzr_id)
        return float(r["crime_rate"]) if r else None

    def crime_rates(self) -> dict[str, float]:
        return {k: float(r["crime_rate"]) for k, r in self._regions.items()}

    def berlin_crime_rate(self) -> float:
        return self._berlin_crime

    def area_stats(self) -> dict[str, dict[str, float]]:
        return self._area_stats

    # --- around a point -----------------------------------------------------------------

    def nearest_stops(
        self, lat: float, lng: float, limit: int = 6, modes: frozenset[str] | None = None
    ) -> list[Stop]:
        layer = self._stops
        d = haversine_m(lat, lng, layer.lat, layer.lng)
        if modes:
            d = np.where([bool(m & modes) for m in self._stop_modes], d, np.inf)
        order = np.lexsort((np.arange(d.size), d))[:limit]
        out = []
        for i in order:
            if not math.isfinite(d[i]):
                break
            s = layer.rows[i]
            out.append(Stop(s["id"], s["name"], tuple(s["modes"]), s["lat"], s["lng"], float(d[i])))
        return out

    def within(self, layer: str, lat: float, lng: float, radius_m: float) -> list[dict]:
        if layer not in POINT_LAYERS:
            raise ValueError(f"unknown layer {layer!r}")
        return self._layers[layer].within(lat, lng, radius_m)

    def nearest_park(self, lat: float, lng: float) -> Park | None:
        if not self._parks:
            return None
        b = self._park_bbox
        # Lower bound of each park's distance: distance to its bounding box.
        cx = np.clip(lng, b[:, 0], b[:, 2])
        cy = np.clip(lat, b[:, 1], b[:, 3])
        lower = haversine_m(lat, lng, cy, cx)
        best_d, best_i = math.inf, -1
        for i in np.argsort(lower, kind="stable"):
            if lower[i] > best_d:
                break
            d = self._park_distance(i, lat, lng)
            if d < best_d - 1e-9 or (abs(d - best_d) <= 1e-9 and i < best_i):
                best_d, best_i = d, int(i)
        p = self._parks[best_i]
        return Park(p["name"], p["area_m2"], float(best_d), p["lat"], p["lng"])

    def _park_distance(self, i: int, lat: float, lng: float) -> float:
        rings = self._park_rings[i]
        if points_in_polygons(np.array([lng]), np.array([lat]), rings)[0]:
            return 0.0
        best = math.inf
        for poly in rings:
            for ring in poly:
                xy = local_xy(lat, lng, ring[:, 1], ring[:, 0])
                seg = np.hstack([xy[:-1], xy[1:]])
                best = min(best, float(point_segment_distance(0.0, 0.0, seg).min()))
        return best

    def nearest_air_station(self, lat: float, lng: float) -> AirStation | None:
        layer = self._air
        if not layer.rows:
            return None
        d = haversine_m(lat, lng, layer.lat, layer.lng)
        i = int(np.argmin(d))
        s = layer.rows[i]
        return AirStation(
            s["code"],
            s["name"],
            s["station_type"],
            s["lqi"],
            s["measured_at"],
            float(d[i]),
            s["lat"],
            s["lng"],
        )

    # --- map layers (results map: Transit, Green) -----------------------------------------

    def stops_in_bbox(
        self, south: float, west: float, north: float, east: float, limit: int = 400
    ) -> list[Stop]:
        layer = self._stops
        idx = np.nonzero(
            (layer.lat >= south) & (layer.lat <= north) & (layer.lng >= west) & (layer.lng <= east)
        )[0][:limit]
        return [
            Stop(
                layer.rows[i]["id"],
                layer.rows[i]["name"],
                tuple(layer.rows[i]["modes"]),
                layer.rows[i]["lat"],
                layer.rows[i]["lng"],
                0.0,
            )
            for i in idx
        ]

    def parks_in_bbox(
        self, south: float, west: float, north: float, east: float, limit: int = 300
    ) -> list[dict]:
        b = self._park_bbox
        idx = np.nonzero(
            (b[:, 0] <= east) & (b[:, 2] >= west) & (b[:, 1] <= north) & (b[:, 3] >= south)
        )[0]
        order = sorted(idx.tolist(), key=lambda i: -self._parks[i]["area_m2"])[:limit]
        return [
            {
                "name": self._parks[i]["name"],
                "area_m2": self._parks[i]["area_m2"],
                "polygons": self._parks[i]["polygons"],
            }
            for i in sorted(order)
        ]

    # --- rent index ---------------------------------------------------------------------

    def rent_rows(self) -> list[dict]:
        return self._rent_rows

    def rent_periods(self) -> dict[str, dict]:
        return self._periods

    def checklist(self) -> list[dict]:
        return self._checklist

    def manifest(self) -> dict:
        return self._manifest

    def planning_area(self, plr_id: str) -> dict | None:
        return self._plr_index.get(plr_id)
