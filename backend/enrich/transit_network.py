"""Route-based offline commute estimate over the VBB weekday-peak network (ADR-0009).

Uses the files `data/vbb_network.py` builds from VBB GTFS (`make demo-stops`). A trip is
modelled door to door:

    walk to a station (≤ ACCESS_KM) → wait for a line → ride it stop by stop
    → [alight, optionally walk ≤ TRANSFER_WALK_KM to another station, wait, ride]…
    → alight → walk to the destination

Ride times are median scheduled times, waits are half the line's peak gap at that
station, and every alighting costs ALIGHT_MIN (platform change or exit). Walking all
the way is always an option. Shortest path by time (Dijkstra); the number of changes is
the number of boardings minus one.

No network access. If the files are missing, `get_network()` returns None and callers
fall back to the straight-line estimate (enrich/commute_estimate.py).
"""

from __future__ import annotations

import csv
import heapq
import itertools
import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from core.logging import get_logger
from enrich.commute_estimate import WALK_DETOUR, WALK_KMH, haversine_km

logger = get_logger(__name__)

NETWORK_DIR = Path(__file__).resolve().parents[1] / "data" / "vbb"
STATIONS_FILE = "network_stations.csv"
RIDES_FILE = "network_rides.csv"
BOARDINGS_FILE = "network_boardings.csv"
META_FILE = "network_meta.json"

ACCESS_KM = 1.2  # walk to/from stations up to this straight-line distance
TRANSFER_WALK_KM = 0.3  # walking links between separate stations (e.g. S+U vs. bus stop)
ALIGHT_MIN = 2.0  # leaving a vehicle: platform change, or exiting the station

# Grid for nearby-station lookups: ~1.1 km × ~1.0 km cells at Berlin's latitude.
_CELL_LAT = 0.01
_CELL_LNG = 0.015


def walk_minutes(km: float) -> float:
    return km * WALK_DETOUR / WALK_KMH * 60


@dataclass
class Route:
    minutes: float
    changes: int
    walk_minutes: float
    legs: list[str]  # human-readable, for debugging and tests

    @property
    def uses_transit(self) -> bool:
        return any(not leg.startswith("walk") for leg in self.legs)


@dataclass
class TransitNetwork:
    stations: dict[str, tuple[str, float, float]]
    rides: dict[tuple[str, str], list[tuple[str, float]]]  # (line, from) -> [(to, minutes)]
    boardings: dict[str, list[tuple[str, float]]]  # station -> [(line, wait)]
    line_names: dict[str, str]
    walk_links: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    _grid: dict[tuple[int, int], list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for sid, (_n, lat, lng) in self.stations.items():
            self._grid.setdefault(self._cell(lat, lng), []).append(sid)
        for sid, (_n, lat, lng) in self.stations.items():
            self.walk_links[sid] = [
                (other, walk_minutes(d))
                for other, d in self.near(lat, lng, TRANSFER_WALK_KM)
                if other != sid
            ]

    @staticmethod
    def _cell(lat: float, lng: float) -> tuple[int, int]:
        return int(math.floor(lat / _CELL_LAT)), int(math.floor(lng / _CELL_LNG))

    def near(self, lat: float, lng: float, radius_km: float) -> list[tuple[str, float]]:
        """Stations within `radius_km` (straight line) of a point, with their distance."""
        ci, cj = self._cell(lat, lng)
        reach_i = int(math.ceil(radius_km / 111.0 / _CELL_LAT))
        reach_j = int(math.ceil(radius_km / (111.0 * math.cos(math.radians(lat))) / _CELL_LNG))
        found = []
        for i in range(ci - reach_i, ci + reach_i + 1):
            for j in range(cj - reach_j, cj + reach_j + 1):
                for sid in self._grid.get((i, j), ()):
                    _n, slat, slng = self.stations[sid]
                    d = haversine_km(lat, lng, slat, slng)
                    if d <= radius_km:
                        found.append((sid, d))
        return found

    def route(self, lat: float, lng: float, dlat: float, dlng: float) -> Route:
        """Fastest door-to-door trip (walking all the way is always a candidate)."""
        direct_walk = walk_minutes(haversine_km(lat, lng, dlat, dlng))
        best = direct_walk
        best_end: tuple | None = None
        egress = {sid: walk_minutes(d) for sid, d in self.near(dlat, dlng, ACCESS_KM)}

        origin = ("O",)
        dist: dict[tuple, float] = {origin: 0.0}
        prev: dict[tuple, tuple] = {}
        counter = itertools.count()  # tie-breaker so the heap never compares nodes
        heap: list = [(0.0, next(counter), origin)]
        while heap:
            t, _, node = heapq.heappop(heap)
            if t > dist.get(node, math.inf) or t >= best:
                continue
            if node == origin:
                nxt = [(("S", sid), walk_minutes(d)) for sid, d in self.near(lat, lng, ACCESS_KM)]
            elif node[0] == "S":
                sid = node[1]
                if sid in egress and t + egress[sid] < best:
                    best, best_end = t + egress[sid], node
                nxt = [(("L", line, sid), wait) for line, wait in self.boardings.get(sid, ())]
                nxt += [(("S", other), w) for other, w in self.walk_links.get(sid, ())]
            else:  # ("L", line, station): on board
                _, line, sid = node
                nxt = [(("L", line, to), m) for to, m in self.rides.get((line, sid), ())]
                nxt.append((("S", sid), ALIGHT_MIN))
            for n2, w in nxt:
                t2 = t + w
                if t2 < dist.get(n2, math.inf):
                    dist[n2], prev[n2] = t2, node
                    heapq.heappush(heap, (t2, next(counter), n2))

        if best_end is None:
            return Route(best, 0, direct_walk, ["walk to destination"])
        return self._describe(prev, dist, best_end, best, egress[best_end[1]])

    def _describe(self, prev, dist, end, total, egress_min) -> Route:
        path = [end]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()  # origin → … → end station
        legs: list[str] = []
        walking = egress_min
        boardings = 0
        board_at: tuple[str, str] | None = None
        for a, b in zip(path, path[1:], strict=False):
            step = dist[b] - dist[a]
            if a[0] == "O" or (a[0] == "S" and b[0] == "S"):
                walking += step
                legs.append(f"walk {step:.0f} min to {self.stations[b[1]][0]}")
            elif a[0] == "S" and b[0] == "L":
                boardings += 1
                board_at = (b[1], a[1])
            elif a[0] == "L" and b[0] == "S" and board_at:
                line, start = board_at
                ride = dist[a] - dist[("S", start)]
                legs.append(
                    f"{self.line_names.get(line, line)} {self.stations[start][0]} → "
                    f"{self.stations[b[1]][0]} ({ride:.0f} min incl. wait)"
                )
                board_at = None
        if egress_min >= 0.5:
            legs.append(f"walk {egress_min:.0f} min to destination")
        return Route(total, max(0, boardings - 1), walking, legs)


def network_from_records(
    stations: Iterable[dict], rides: Iterable[dict], boardings: Iterable[dict]
) -> TransitNetwork | None:
    """Build a routable network from rows shaped like the network_*.csv files.

    Shared by `load_network` (CSV files) and the Lifestyle Match data build, which
    routes over an in-memory network extracted straight from the GTFS zip.
    """
    station_map = {
        str(r["station_id"]): (r["name"], float(r["lat"]), float(r["lng"])) for r in stations
    }
    ride_map: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    line_names: dict[str, str] = {}
    for r in rides:
        ride_map[(r["line"], r["from_station"])].append((r["to_station"], float(r["minutes"])))
        line_names[r["line"]] = r["line_name"]
    boarding_map: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for r in boardings:
        boarding_map[r["station"]].append((r["line"], float(r["wait_minutes"])))
    if not station_map or not ride_map:
        return None
    return TransitNetwork(station_map, dict(ride_map), dict(boarding_map), line_names)


def load_network(directory: Path = NETWORK_DIR) -> TransitNetwork | None:
    files = [directory / n for n in (STATIONS_FILE, RIDES_FILE, BOARDINGS_FILE)]
    if not all(f.is_file() for f in files):
        return None

    def rows(path: Path):
        with path.open(encoding="utf-8", newline="") as f:
            yield from csv.DictReader(f)

    return network_from_records(rows(files[0]), rows(files[1]), rows(files[2]))


@lru_cache(maxsize=1)
def get_network() -> TransitNetwork | None:
    net = load_network()
    if net is None:
        logger.info(
            "VBB network not found in %s — commute estimates use straight-line distance. "
            "Run `make demo-stops` once while online.",
            NETWORK_DIR,
        )
    return net
