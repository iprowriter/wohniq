"""Load the `make berlin-data` build into Supabase (live mode).

    uv run python -m data.berlin.load        # or: make berlin-load

Replaces the contents of the berlin_* tables in one transaction (TRUNCATE + COPY), so a
failed load leaves the previous data in place. Also backfills listing.year_built for the
seeded synthetic listings. Needs migration 0003 (`make migrate`). See ADR-0016.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import psycopg

from berlin import files
from core.config import settings
from data.synthetic import year_built_for

TABLES = (
    "berlin_address",
    "berlin_planning_area",
    "berlin_district_region",
    "berlin_stop",
    "berlin_school",
    "berlin_kita",
    "berlin_park",
    "berlin_playground",
    "berlin_accident",
    "berlin_air_station",
    "berlin_rent_row",
    "berlin_dataset",
)


def point(lat: float | str, lng: float | str) -> str:
    return f"SRID=4326;POINT({lng} {lat})"


def multipolygon(polygons: list) -> str:
    def ring(r: list) -> str:
        return "(" + ",".join(f"{x} {y}" for x, y in r) + ")"

    return (
        "SRID=4326;MULTIPOLYGON("
        + ",".join("(" + ",".join(ring(r) for r in poly) + ")" for poly in polygons)
        + ")"
    )


def _copy(cur, table: str, columns: tuple[str, ...], rows) -> int:
    n = 0
    with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as cp:
        for row in rows:
            cp.write_row(row)
            n += 1
    return n


def load(build_dir: Path, database_url: str) -> dict[str, int]:
    manifest = files.read_json(files.MANIFEST, build_dir)
    counts: dict[str, int] = {}
    with psycopg.connect(database_url, autocommit=False) as conn, conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout = 0")
        cur.execute(f"TRUNCATE {', '.join(TABLES)}")

        counts["berlin_address"] = _copy(
            cur,
            "berlin_address",
            (
                "id",
                "street",
                "house_number",
                "postcode",
                "district",
                "location_class",
                "east",
                "plr_id",
                "search_key",
                "lat",
                "lng",
                "geog",
            ),
            (
                (
                    int(r["id"]),
                    r["street"],
                    r["house_number"],
                    r["postcode"],
                    r["district"],
                    r["location_class"],
                    r["east"] == "1",
                    r["plr_id"],
                    r["search_key"],
                    float(r["lat"]),
                    float(r["lng"]),
                    point(r["lat"], r["lng"]),
                )
                for r in files.read_csv_gz(files.ADDRESSES, build_dir)
            ),
        )

        areas = files.read_json(files.AREAS, build_dir)
        stats = files.read_json(files.AREA_STATS, build_dir)
        counts["berlin_planning_area"] = _copy(
            cur,
            "berlin_planning_area",
            ("id", "name", "bzr_id", "bzr_name", "district", "lat", "lng", "stats", "geog"),
            (
                (
                    a["id"],
                    a["name"],
                    a["bzr_id"],
                    a["bzr_name"],
                    a["district"],
                    a["lat"],
                    a["lng"],
                    json.dumps(stats["areas"].get(a["id"], {})),
                    multipolygon(a["polygons"]),
                )
                for a in areas["planning_areas"]
            ),
        )
        counts["berlin_district_region"] = _copy(
            cur,
            "berlin_district_region",
            ("id", "name", "district", "crime_rate"),
            (
                (r["id"], r["name"], r["district"], r.get("crime_rate"))
                for r in areas["district_regions"]
            ),
        )

        counts["berlin_stop"] = _copy(
            cur,
            "berlin_stop",
            ("id", "name", "modes", "lat", "lng", "geog"),
            (
                (s["id"], s["name"], s["modes"], s["lat"], s["lng"], point(s["lat"], s["lng"]))
                for s in files.read_json(files.STOPS, build_dir)
            ),
        )
        counts["berlin_school"] = _copy(
            cur,
            "berlin_school",
            ("id", "name", "kind", "school_type", "lat", "lng", "geog"),
            (
                (
                    i + 1,
                    s["name"],
                    s["kind"],
                    s["school_type"],
                    s["lat"],
                    s["lng"],
                    point(s["lat"], s["lng"]),
                )
                for i, s in enumerate(files.read_json(files.SCHOOLS, build_dir))
            ),
        )
        counts["berlin_kita"] = _copy(
            cur,
            "berlin_kita",
            ("id", "name", "places", "lat", "lng", "geog"),
            (
                (i + 1, k["name"], k["places"], k["lat"], k["lng"], point(k["lat"], k["lng"]))
                for i, k in enumerate(files.read_json(files.KITAS, build_dir))
            ),
        )
        counts["berlin_park"] = _copy(
            cur,
            "berlin_park",
            ("id", "name", "area_m2", "lat", "lng", "geog"),
            (
                (i + 1, p["name"], p["area_m2"], p["lat"], p["lng"], multipolygon(p["polygons"]))
                for i, p in enumerate(files.read_json(files.PARKS, build_dir))
            ),
        )
        counts["berlin_playground"] = _copy(
            cur,
            "berlin_playground",
            ("id", "name", "lat", "lng", "geog"),
            (
                (i + 1, p["name"], p["lat"], p["lng"], point(p["lat"], p["lng"]))
                for i, p in enumerate(files.read_json(files.PLAYGROUNDS, build_dir))
            ),
        )
        counts["berlin_accident"] = _copy(
            cur,
            "berlin_accident",
            ("id", "category", "bike", "pedestrian", "lat", "lng", "geog"),
            (
                (
                    i + 1,
                    int(r["category"]),
                    r["bike"] == "1",
                    r["pedestrian"] == "1",
                    float(r["lat"]),
                    float(r["lng"]),
                    point(r["lat"], r["lng"]),
                )
                for i, r in enumerate(files.read_csv_gz(files.ACCIDENTS, build_dir))
            ),
        )
        air = files.read_json(files.AIR, build_dir)
        counts["berlin_air_station"] = _copy(
            cur,
            "berlin_air_station",
            ("code", "name", "station_type", "lqi", "measured_at", "lat", "lng", "geog"),
            (
                (
                    s["code"],
                    s["name"],
                    s["station_type"],
                    s["lqi"],
                    s["measured_at"],
                    s["lat"],
                    s["lng"],
                    point(s["lat"], s["lng"]),
                )
                for s in air["stations"]
            ),
        )
        rent = files.read_json(files.RENT_TABLE, build_dir)
        counts["berlin_rent_row"] = _copy(
            cur,
            "berlin_rent_row",
            ("row", "location", "period", "size_min", "size_max", "low", "mean", "high"),
            (
                (
                    r["row"],
                    r["location"],
                    r["period"],
                    r["size_min"],
                    r["size_max"],
                    r["low"],
                    r["mean"],
                    r["high"],
                )
                for r in rent["rows"]
            ),
        )
        documents = {
            "manifest": manifest,
            "rent_periods": rent["periods"],
            "checklist": files.read_json(files.CHECKLIST, build_dir),
            "air": {"snapshot": air["snapshot"]},
            "crime": areas["crime"],
            "area_stats": {k: v for k, v in stats.items() if k != "areas"},
        }
        counts["berlin_dataset"] = _copy(
            cur,
            "berlin_dataset",
            ("name", "content"),
            (
                (name, json.dumps(content, ensure_ascii=False))
                for name, content in documents.items()
            ),
        )

        # Synthetic listings: the building year is a function of the id (data/synthetic.py).
        cur.execute("SELECT id FROM listing WHERE is_synthetic")
        updates = [(year_built_for(lid), lid) for (lid,) in cur.fetchall()]
        cur.executemany("UPDATE listing SET year_built = %s WHERE id = %s", updates)
        counts["listing.year_built"] = len(updates)
        conn.commit()

    with psycopg.connect(database_url, autocommit=True) as conn:
        for table in TABLES:
            conn.execute(f"ANALYZE {table}")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--build", type=Path, default=files.BUILD_DIR)
    args = ap.parse_args(argv)
    if not settings.database_url.strip():
        print("error: DATABASE_URL is empty; nothing to load into.", file=sys.stderr)
        return 1
    if not files.is_built(args.build):
        print("error: no build found. Run `make berlin-data` first.", file=sys.stderr)
        return 1
    t0 = time.monotonic()
    counts = load(args.build, settings.database_url)
    for table, n in counts.items():
        print(f"  {table:24} {n:>8,}")
    print(f"Loaded in {time.monotonic() - t0:.0f} s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
