"""A small synthetic GTFS feed with the traps the real VBB data contains.

Stations (each with a platform child that stop_times reference):

        D (north)
        |  S1, every 10 min, 8 min ride
    A --+-- B -- C        U1 A→B→C, every 5 min, 10 min per hop (+ reverse direction)
  (west)|  (centre)       R1 A→C express, weekdays, removed on Tue 2026-01-06
        F  bus stop ~200 m from B; bus X F→E every 10 min, 12 min ride
        |
        E (south)

Shortcuts to E that must NOT be used in the weekday 07–09 peak:
  * a single U1 diversion trip A→E (5 min), same line and direction — too rare
  * night line N1 A→E — runs 22:00–02:00
  * weekend line W1 A→E — Saturday/Sunday only
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

STATIONS = {
    "A": ("U Westend", 52.50, 13.30),
    "B": ("S+U Mitte", 52.50, 13.40),
    "C": ("U Ostend", 52.50, 13.50),
    "D": ("S Nord", 52.56, 13.40),
    "E": ("Süd", 52.44, 13.40),
    "F": ("Mitte/Busplatz", 52.5018, 13.4005),
}


def _table(rows: list[list]) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def _hhmm(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60:02d}:{m % 60:02d}:00"


def build_gtfs(path: Path) -> Path:
    stops = [["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"]]
    for sid, (name, lat, lng) in STATIONS.items():
        stops.append([sid, name, lat, lng, "1", ""])
        stops.append([f"{sid}:1", f"{name} Gleis 1", lat + 0.0001, lng, "0", sid])

    routes = [["route_id", "route_short_name", "route_type"]]
    trips = [["route_id", "service_id", "trip_id", "direction_id"]]
    stop_times = [["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"]]

    def line(route_id, name, route_type, service, direction, hops, first, last, every, tag=""):
        if [route_id, name, route_type] not in routes:
            routes.append([route_id, name, route_type])
        start = first
        n = 0
        while start <= last:
            trip_id = f"{route_id}{tag}-{direction}-{n}"
            trips.append([route_id, service, trip_id, direction])
            t = start
            for seq, (stop, ride) in enumerate(hops):
                t += ride
                stop_times.append([trip_id, _hhmm(t), _hhmm(t), f"{stop}:1", seq + 1])
            start += every
            n += 1

    # (stop, minutes from previous stop); first hop ride is 0.
    line("U1", "U1", "1", "WD", "0", [("A", 0), ("B", 10), ("C", 10)], 6 * 60, 10 * 60, 5)
    line("U1", "U1", "1", "WD", "1", [("C", 0), ("B", 10), ("A", 10)], 6 * 60, 10 * 60, 5)
    line("S1", "S1", "2", "WD", "0", [("D", 0), ("B", 8)], 6 * 60, 10 * 60, 10)
    line("X", "X", "3", "WD", "0", [("F", 0), ("E", 12)], 6 * 60, 10 * 60, 10)
    line("R1", "R1", "2", "EXP", "0", [("A", 0), ("C", 6)], 6 * 60, 10 * 60, 20)
    # One-off diversion on the regular U1 line and direction (like VBB's S45 via Alexanderplatz).
    line("U1", "U1", "1", "WD", "0", [("A", 0), ("E", 5)], 7 * 60 + 30, 7 * 60 + 30, 60, tag="div")
    line("N1", "N1", "3", "WD", "0", [("A", 0), ("E", 4)], 22 * 60, 26 * 60, 10)  # night
    line("W1", "W1", "1", "WE", "0", [("A", 0), ("E", 4)], 6 * 60, 10 * 60, 5)  # weekend

    calendar = [
        [
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        ],
        ["WD", 1, 1, 1, 1, 1, 0, 0, "20260105", "20260331"],
        ["EXP", 1, 1, 1, 1, 1, 0, 0, "20260105", "20260331"],
        ["WE", 0, 0, 0, 0, 0, 1, 1, "20260105", "20260331"],
    ]
    calendar_dates = [["service_id", "date", "exception_type"], ["EXP", "20260106", "2"]]

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("stops.txt", "\ufeff" + _table(stops))
        zf.writestr("routes.txt", _table(routes))
        zf.writestr("trips.txt", _table(trips))
        zf.writestr("stop_times.txt", _table(stop_times))
        zf.writestr("calendar.txt", _table(calendar))
        zf.writestr("calendar_dates.txt", _table(calendar_dates))
    return path
