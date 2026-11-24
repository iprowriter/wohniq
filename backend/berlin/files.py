"""Where `make berlin-data` writes its output, and how to read it back.

The build directory is gitignored (ADR-0016). Offline demo mode reads these files directly;
`make berlin-load` copies the same content into Supabase.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

BUILD_DIR = Path(__file__).resolve().parents[1] / "data" / "berlin" / "build"

MANIFEST = "manifest.json"
RENT_TABLE = "rent_table.json"
CHECKLIST = "checklist.json"
ADDRESSES = "addresses.csv.gz"
AREAS = "areas.json"  # planning areas + district regions (outlines, crime)
STOPS = "stops.json"
SCHOOLS = "schools.json"
KITAS = "kitas.json"
PARKS = "parks.json"
PLAYGROUNDS = "playgrounds.json"
AIR = "air.json"
ACCIDENTS = "accidents.csv.gz"
AREA_STATS = "area_stats.json"

ADDRESS_COLUMNS = (
    "id",
    "street",
    "house_number",
    "postcode",
    "district",
    "location_class",
    "east",
    "plr_id",
    "lat",
    "lng",
    "search_key",
)
ACCIDENT_COLUMNS = ("lat", "lng", "category", "bike", "pedestrian")


class BuildMissing(RuntimeError):
    """The Berlin data hasn't been built on this machine yet."""


def path(name: str, build_dir: Path | None = None) -> Path:
    p = (build_dir or BUILD_DIR) / name
    if not p.is_file():
        raise BuildMissing(f"{p} is missing. Run `make berlin-data` (see ADR-0016).")
    return p


def is_built(build_dir: Path | None = None) -> bool:
    return ((build_dir or BUILD_DIR) / MANIFEST).is_file()


def write_json(name: str, data: Any, build_dir: Path) -> Path:
    p = build_dir / name
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def read_json(name: str, build_dir: Path | None = None) -> Any:
    return json.loads(path(name, build_dir).read_text(encoding="utf-8"))


def write_csv_gz(name: str, columns: tuple[str, ...], rows: list[tuple], build_dir: Path) -> Path:
    p = build_dir / name
    # mtime=0 keeps the gzip bytes identical across rebuilds of the same input.
    with gzip.GzipFile(p, "wb", mtime=0) as raw, open_text(raw) as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        w.writerows(rows)
    return p


def read_csv_gz(name: str, build_dir: Path | None = None) -> Iterator[dict[str, str]]:
    with gzip.open(path(name, build_dir), "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def open_text(raw):
    import io

    return io.TextIOWrapper(raw, encoding="utf-8", newline="")
