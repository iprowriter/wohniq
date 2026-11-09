"""Build a compact weekday-peak transit network from VBB GTFS (ADR-0009).

Input: the VBB GTFS zip (`make demo-stops` downloads it). Output: four small files in
`data/vbb/` that `enrich/transit_network.py` routes over, with no network access:

    network_stations.csv   station_id, name, lat, lng
    network_rides.csv      line, line_name, route_type, from_station, to_station, minutes, trips
    network_boardings.csv  line, station, departures, wait_minutes
    network_meta.json      reference date, peak window, counts, thresholds

Method:
  * Reference day: the Tue/Wed/Thu with the most active services in the first six weeks
    of the feed (avoids public holidays), unless a date is given.
  * Peak window: departures between 07:00 and 09:00 on that day.
  * A "line" is a GTFS route in one direction. Ride time between consecutive stations is
    the median scheduled time of the trips in the window.
  * Waiting time when boarding a line at a station is half the average gap between its
    departures there during the window.
  * A connection served fewer than MIN_TRIPS times in the window is dropped, so one-off
    diversions and rare variants can't create shortcuts.

stop_times.txt is large (tens of millions of rows), so it is streamed and only rows of
trips active on the reference day, and only around the window, are kept in memory.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from enrich.transit_network import (
    BOARDINGS_FILE,
    META_FILE,
    NETWORK_DIR,
    RIDES_FILE,
    STATIONS_FILE,
)

PEAK_START_MIN = 7 * 60  # 07:00
PEAK_END_MIN = 9 * 60  # 09:00 (exclusive)
LOOKAHEAD_MIN = 60  # keep rows this long after the window so late departures reach their next stop
MIN_TRIPS = 2  # a connection must run at least this often in the window (≈ hourly)
CANDIDATE_DAYS = 42  # search this many days from the feed start for the reference weekday
_WEEKDAY_COLS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass
class Network:
    stations: dict[str, tuple[str, float, float]] = field(default_factory=dict)
    rides: list[dict] = field(default_factory=list)
    boardings: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _csv(zf: zipfile.ZipFile, name: str) -> Iterator[dict]:
    with zf.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))


def _gtfs_minutes(value: str) -> float | None:
    """'HH:MM:SS' (hours may exceed 24) → minutes after midnight."""
    parts = value.strip().split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = (int(p) for p in parts)
    except ValueError:
        return None
    return h * 60 + m + s / 60


def _parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y%m%d").date()


def active_services(
    calendar: list[dict], exceptions: dict[date, list[tuple[str, str]]], day: date
) -> set[str]:
    """Service ids running on `day` (calendar.txt rules + calendar_dates.txt exceptions)."""
    col = _WEEKDAY_COLS[day.weekday()]
    active = {
        row["service_id"]
        for row in calendar
        if row.get(col) == "1"
        and _parse_date(row["start_date"]) <= day <= _parse_date(row["end_date"])
    }
    for service_id, exception_type in exceptions.get(day, []):
        if exception_type == "1":
            active.add(service_id)
        elif exception_type == "2":
            active.discard(service_id)
    return active


def pick_reference_date(
    calendar: list[dict],
    exceptions: dict[date, list[tuple[str, str]]],
    override: date | None = None,
) -> tuple[date, set[str]]:
    """The busiest Tue/Wed/Thu early in the feed (or `override`), with its active services."""
    if override is not None:
        return override, active_services(calendar, exceptions, override)
    starts = [_parse_date(r["start_date"]) for r in calendar] + list(exceptions)
    if not starts:
        raise ValueError("GTFS feed has no calendar.txt or calendar_dates.txt dates")
    first = min(starts)
    best: tuple[int, date, set[str]] | None = None
    for offset in range(CANDIDATE_DAYS):
        day = first + timedelta(days=offset)
        if day.weekday() not in (1, 2, 3):  # Tue, Wed, Thu
            continue
        services = active_services(calendar, exceptions, day)
        if best is None or len(services) > best[0]:
            best = (len(services), day, services)
    if best is None or best[0] == 0:
        raise ValueError("no weekday with active services found in the GTFS feed")
    return best[1], best[2]


def extract_network(gtfs_zip: Path, *, reference_date: date | None = None) -> Network:
    with zipfile.ZipFile(gtfs_zip) as zf:
        names = set(zf.namelist())
        calendar = list(_csv(zf, "calendar.txt")) if "calendar.txt" in names else []
        exceptions: dict[date, list[tuple[str, str]]] = defaultdict(list)
        if "calendar_dates.txt" in names:
            for row in _csv(zf, "calendar_dates.txt"):
                exceptions[_parse_date(row["date"])].append(
                    (row["service_id"], row["exception_type"].strip())
                )
        day, services = pick_reference_date(calendar, exceptions, reference_date)

        routes = {
            r["route_id"]: (
                r.get("route_short_name") or r.get("route_long_name") or "",
                r.get("route_type", ""),
            )
            for r in _csv(zf, "routes.txt")
        }
        trip_line: dict[str, str] = {}
        for t in _csv(zf, "trips.txt"):
            if t["service_id"] in services and t["route_id"] in routes:
                direction = t.get("direction_id") or t.get("trip_headsign") or ""
                trip_line[t["trip_id"]] = f"{t['route_id']}|{direction}"

        parent: dict[str, str] = {}
        coords: dict[str, tuple[str, float, float]] = {}
        for s in _csv(zf, "stops.txt"):
            sid = s["stop_id"]
            parent[sid] = s.get("parent_station") or sid
            try:
                lat, lng = float(s["stop_lat"]), float(s["stop_lon"])
            except (KeyError, ValueError):
                continue
            if not s.get("parent_station"):  # a station, or a stop without a station
                coords[sid] = (s.get("stop_name", "").strip(), lat, lng)
            else:
                coords.setdefault(parent[sid], (s.get("stop_name", "").strip(), lat, lng))

        # Stream stop_times, keeping only active trips around the window.
        lo, hi = PEAK_START_MIN, PEAK_END_MIN + LOOKAHEAD_MIN
        by_trip: dict[str, list[tuple[int, float, str]]] = defaultdict(list)
        with zf.open("stop_times.txt") as raw:
            reader = csv.reader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
            header = next(reader)
            i_trip, i_stop = header.index("trip_id"), header.index("stop_id")
            i_seq, i_dep = header.index("stop_sequence"), header.index("departure_time")
            i_arr = header.index("arrival_time")
            for row in reader:
                if row[i_trip] not in trip_line:
                    continue
                t = _gtfs_minutes(row[i_dep] or row[i_arr])
                if t is None or not lo <= t <= hi:
                    continue
                by_trip[row[i_trip]].append(
                    (int(row[i_seq]), t, parent.get(row[i_stop], row[i_stop]))
                )

    ride_times: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    departures: dict[tuple[str, str], int] = defaultdict(int)
    for trip_id, stops in by_trip.items():
        line = trip_line[trip_id]
        stops.sort()
        for (_, dep_a, a), (_, dep_b, b) in zip(stops, stops[1:], strict=False):
            if a == b or not PEAK_START_MIN <= dep_a < PEAK_END_MIN:
                continue
            ride_times[(line, a, b)].append(max(0.0, dep_b - dep_a))
            departures[(line, a)] += 1

    window = PEAK_END_MIN - PEAK_START_MIN
    net = Network()
    boarding_keys: set[tuple[str, str]] = set()
    for (line, a, b), times in ride_times.items():
        if len(times) < MIN_TRIPS or a not in coords or b not in coords:
            continue
        route_id = line.split("|", 1)[0]
        name, route_type = routes[route_id]
        net.rides.append(
            {
                "line": line,
                "line_name": name,
                "route_type": route_type,
                "from_station": a,
                "to_station": b,
                "minutes": round(statistics.median(times), 2),
                "trips": len(times),
            }
        )
        boarding_keys.add((line, a))
        net.stations[a], net.stations[b] = coords[a], coords[b]
    for line, station in sorted(boarding_keys):
        count = departures[(line, station)]
        net.boardings.append(
            {
                "line": line,
                "station": station,
                "departures": count,
                "wait_minutes": round(window / count / 2, 2),
            }
        )
    net.rides.sort(key=lambda r: (r["line"], r["from_station"], r["to_station"]))
    net.meta = {
        "reference_date": day.isoformat(),
        "weekday": day.strftime("%A"),
        "peak_window": "07:00-09:00",
        "min_trips_per_connection": MIN_TRIPS,
        "stations": len(net.stations),
        "rides": len(net.rides),
        "boardings": len(net.boardings),
        "active_trips_in_window": len(by_trip),
    }
    return net


def write_network(net: Network, directory: Path = NETWORK_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    def write(name: str, fields: list[str], rows: list[dict]) -> None:
        tmp = directory / (name + ".part")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(directory / name)  # never leave a half-written file behind

    write(
        STATIONS_FILE,
        ["station_id", "name", "lat", "lng"],
        [
            {"station_id": sid, "name": n, "lat": f"{lat:.6f}", "lng": f"{lng:.6f}"}
            for sid, (n, lat, lng) in sorted(net.stations.items())
        ],
    )
    write(
        RIDES_FILE,
        ["line", "line_name", "route_type", "from_station", "to_station", "minutes", "trips"],
        net.rides,
    )
    write(BOARDINGS_FILE, ["line", "station", "departures", "wait_minutes"], net.boardings)
    (directory / META_FILE).write_text(json.dumps(net.meta, indent=2) + "\n", encoding="utf-8")
