"""The "Around this flat" measures that are compared across Berlin's 542 planning areas.

`gather_point` asks the Berlin data everything about one point once (concurrently when the
data is remote, i.e. Supabase); `measures_from` turns that into the numbers the build
compares across planning areas, and berlin/profile.py into the cards. A flat and the area
figures it's compared with are therefore always measured the same way.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from berlin.repository import AirStation, Area, BerlinData, Park, Stop

RAIL = frozenset({"sbahn", "ubahn"})

AREA_MEASURES: dict[str, str] = {
    "rail_stop_m": "Distance to the nearest S- or U-Bahn station (m)",
    "stop_m": "Distance to the nearest stop of any kind (m)",
    "schools_1km": "Schools within 1 km (excluding adult education)",
    "kitas_500m": "Kitas within 500 m",
    "kita_places_500m": "Permitted Kita places within 500 m",
    "park_m": "Distance to the nearest green space of 1 ha or more (m)",
    "playgrounds_500m": "Playgrounds within 500 m",
    "accidents_300m": "Road accidents with injuries within 300 m (2025)",
}


@dataclass
class PointFacts:
    rail: Stop | None
    any_stop: Stop | None
    schools: list[dict]  # within 1 km, adult education excluded
    kitas: list[dict]  # within 500 m
    park: Park | None
    playgrounds: list[dict]  # within 500 m
    accidents: list[dict]  # within 300 m
    air: AirStation | None = None
    area: Area | None = None


def gather_point(data: BerlinData, lat: float, lng: float, *, full: bool = True) -> PointFacts:
    """Everything about one point. `full` adds the air station and the planning area."""
    calls = {
        "rail": lambda: data.nearest_stops(lat, lng, limit=1, modes=RAIL),
        "any_stop": lambda: data.nearest_stops(lat, lng, limit=1),
        "schools": lambda: data.within("schools", lat, lng, 1000),
        "kitas": lambda: data.within("kitas", lat, lng, 500),
        "park": lambda: data.nearest_park(lat, lng),
        "playgrounds": lambda: data.within("playgrounds", lat, lng, 500),
        "accidents": lambda: data.within("accidents", lat, lng, 300),
    }
    if full:
        calls["air"] = lambda: data.nearest_air_station(lat, lng)
        calls["area"] = lambda: data.area_at(lat, lng)
    if getattr(data, "remote", False):
        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            futures = {k: pool.submit(f) for k, f in calls.items()}
            r = {k: f.result() for k, f in futures.items()}
    else:
        r = {k: f() for k, f in calls.items()}
    return PointFacts(
        rail=r["rail"][0] if r["rail"] else None,
        any_stop=r["any_stop"][0] if r["any_stop"] else None,
        schools=[s for s in r["schools"] if s["kind"] != "adult"],
        kitas=r["kitas"],
        park=r["park"],
        playgrounds=r["playgrounds"],
        accidents=r["accidents"],
        air=r.get("air"),
        area=r.get("area"),
    )


def measures_from(f: PointFacts) -> dict[str, float]:
    out: dict[str, float] = {}
    if f.rail:
        out["rail_stop_m"] = f.rail.distance_m
    if f.any_stop:
        out["stop_m"] = f.any_stop.distance_m
    out["schools_1km"] = len(f.schools)
    out["kitas_500m"] = len(f.kitas)
    out["kita_places_500m"] = sum(k["places"] or 0 for k in f.kitas)
    if f.park:
        out["park_m"] = f.park.distance_m
    out["playgrounds_500m"] = len(f.playgrounds)
    out["accidents_300m"] = len(f.accidents)
    return out


def measure_point(data: BerlinData, lat: float, lng: float) -> dict[str, float]:
    return measures_from(gather_point(data, lat, lng, full=False))
