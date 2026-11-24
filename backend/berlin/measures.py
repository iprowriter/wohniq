"""The "Around this flat" measures that are compared across Berlin's 542 planning areas.

One function measures a point; the build runs it over a sample of every planning area's
addresses (data/berlin/build.py) and the place profile runs it for a flat, so a flat and the
area figures it's compared with are always measured the same way.
"""

from __future__ import annotations

from berlin.repository import BerlinData

RAIL = frozenset({"sbahn", "ubahn"})

# key → (what it is, whether lower values mean "closer"/"fewer")
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


def measure_point(data: BerlinData, lat: float, lng: float) -> dict[str, float]:
    out: dict[str, float] = {}
    rail = data.nearest_stops(lat, lng, limit=1, modes=RAIL)
    if rail:
        out["rail_stop_m"] = rail[0].distance_m
    any_stop = data.nearest_stops(lat, lng, limit=1)
    if any_stop:
        out["stop_m"] = any_stop[0].distance_m
    out["schools_1km"] = sum(
        1 for s in data.within("schools", lat, lng, 1000) if s["kind"] != "adult"
    )
    kitas = data.within("kitas", lat, lng, 500)
    out["kitas_500m"] = len(kitas)
    out["kita_places_500m"] = sum(k["places"] or 0 for k in kitas)
    park = data.nearest_park(lat, lng)
    if park:
        out["park_m"] = park.distance_m
    out["playgrounds_500m"] = len(data.within("playgrounds", lat, lng, 500))
    out["accidents_300m"] = len(data.within("accidents", lat, lng, 300))
    return out
