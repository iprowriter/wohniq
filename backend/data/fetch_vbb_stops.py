"""Extract stops and a weekday-peak transit network from VBB's open GTFS data (once, online).

Offline commute estimates need two things without calling an API:
  * `data/vbb/stops.csv` — Berlin-area stops, to turn a work location ("Alexanderplatz")
    into coordinates (enrich/places.py).
  * `data/vbb/network_*.csv` — lines, ride times and peak waits, to route door to door
    (data/vbb_network.py builds it, enrich/transit_network.py routes over it; ADR-0009).

Both come from the same GTFS download. Not committed to git: like the demo photos, each
machine fetches them once. Data: VBB Verkehrsverbund Berlin-Brandenburg GmbH, open GTFS
timetable data (see daten.berlin.de for the licence and attribution).

    uv run python -m data.fetch_vbb_stops                  # or: make demo-stops
    uv run python -m data.fetch_vbb_stops --url URL        # if the feed URL has moved
    uv run python -m data.fetch_vbb_stops --from-zip GTFS.zip   # already-downloaded feed
    uv run python -m data.fetch_vbb_stops --date 2026-11-10     # pick the reference weekday
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import httpx

from data.kieze import BERLIN_BBOX
from data.vbb_network import extract_network, write_network
from enrich.places import STOPS_CSV
from enrich.transit_network import NETWORK_DIR

# VBB's stable link to the current GTFS feed (redirects to the dated zip).
DEFAULT_GTFS_URL = "https://www.vbb.de/vbbgtfs"

# GTFS location_type: "" / 0 = stop, 1 = station. Skip entrances (2), nodes (3),
# boarding areas (4) — they duplicate their station's name.
_KEEP_TYPES = {"", "0", "1"}


def _in_berlin(lat: float, lng: float) -> bool:
    b = BERLIN_BBOX
    return b["lat_min"] <= lat <= b["lat_max"] and b["lng_min"] <= lng <= b["lng_max"]


def extract_stops(gtfs_zip: Path) -> list[dict]:
    """Berlin-area stops/stations from a GTFS zip (platforms folded into their station)."""
    with zipfile.ZipFile(gtfs_zip) as zf, zf.open("stops.txt") as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
        rows = []
        for r in reader:
            if r.get("location_type", "") not in _KEEP_TYPES or r.get("parent_station"):
                continue
            try:
                lat, lng = float(r["stop_lat"]), float(r["stop_lon"])
            except (KeyError, ValueError):
                continue
            if r.get("stop_name") and _in_berlin(lat, lng):
                rows.append(
                    {
                        "name": r["stop_name"].strip(),
                        "lat": f"{lat:.6f}",
                        "lng": f"{lng:.6f}",
                        "location_type": r.get("location_type", ""),
                    }
                )
    return rows


def write_stops(rows: list[dict], target: Path = STOPS_CSV) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".csv.part")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "lat", "lng", "location_type"])
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(target)  # never leave a half-written file behind


def download(url: str, dest: Path) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as resp:
        resp.raise_for_status()
        with dest.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Berlin stops from VBB GTFS.")
    parser.add_argument("--url", default=DEFAULT_GTFS_URL, help="GTFS zip URL")
    parser.add_argument("--from-zip", type=Path, help="Use a local GTFS zip instead")
    parser.add_argument(
        "--date", type=date.fromisoformat, help="Reference weekday YYYY-MM-DD (default: auto)"
    )
    args = parser.parse_args()

    try:
        if args.from_zip:
            process(args.from_zip, args.date)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                zip_path = Path(tmp) / "gtfs.zip"
                print(f"downloading {args.url} …")
                download(args.url, zip_path)
                process(zip_path, args.date)
    except (httpx.HTTPError, zipfile.BadZipFile, KeyError, OSError) as exc:
        sys.exit(f"failed to get VBB data: {exc}")
    print("Data: VBB Verkehrsverbund Berlin-Brandenburg GmbH (open GTFS data).")


def process(gtfs_zip: Path, reference_date: date | None) -> None:
    rows = extract_stops(gtfs_zip)
    if not rows:
        sys.exit("no Berlin-area stops found in the GTFS feed; nothing written")
    write_stops(rows)
    print(f"stops: {len(rows)} Berlin-area stops -> {STOPS_CSV}")

    print("building weekday-peak network (reads the full timetable; can take a few minutes) …")
    try:
        net = extract_network(gtfs_zip, reference_date=reference_date)
    except (KeyError, ValueError) as exc:
        # Stops alone still enable straight-line estimates; don't fail the whole step.
        print(f"warning: network not built ({exc}); commute estimates stay straight-line")
        return
    write_network(net)
    m = net.meta
    print(
        f"network: {m['stations']} stations, {m['rides']} connections, "
        f"{m['boardings']} boarding points; {m['weekday']} {m['reference_date']} "
        f"{m['peak_window']} -> {NETWORK_DIR}"
    )


if __name__ == "__main__":
    main()
