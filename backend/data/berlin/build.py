"""Build the Berlin open-data files for the rent check, Around this flat and Right now.

    uv run python -m data.berlin.build                 # or: make berlin-data
    BERLIN_RAW_DIR=/path/to/berlinvisualized/data/raw make berlin-data

Reads the checksummed raw files (sources.py), writes compact derived files to
backend/data/berlin/build/ (gitignored), then measures every planning area through the same
in-memory repository the app uses, so area comparisons match what a flat's page shows.
Takes a few minutes; most of it is the 400,505 addresses. See ADR-0016.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from berlin import files
from berlin.geo import haversine_m, points_in_polygons
from berlin.text import address_key, clean_house_number
from data.berlin import sources
from data.berlin.mietspiegel import PERIODS, read_checklist, read_rent_table
from data.berlin.utm import utm_to_latlng
from data.lifestyle.geo import simplify_ring

AREA_TOLERANCE_M = 3.0  # outline simplification (planning areas, regions, parks)
PARK_MIN_M2 = 10_000  # "nearest green space of 1 ha or more"
STATS_SAMPLE = 60  # addresses measured per planning area for its typical values

LOCATION_CLASS = {"einfach": "simple", "mittel": "medium", "gut": "good"}
# GTFS route_type → our transport type (VBB uses the extended types).
ROUTE_TYPES = {
    "109": "sbahn",
    "400": "ubahn",
    "401": "ubahn",
    "402": "ubahn",
    "900": "tram",
    "700": "bus",
    "3": "bus",
    "1000": "ferry",
    "4": "ferry",
    "100": "regional",
    "106": "regional",
    "2": "regional",
}
SCHOOL_KIND = {
    "Grundschule": "primary",
    "Integrierte Sekundarschule": "secondary",
    "Gymnasium": "secondary",
    "Gemeinschaftsschule": "secondary",
    "Freie Waldorfschule": "secondary",
    "Kombinierte allgemein bildende Schule": "secondary",
    "Oberstufenzentrum": "vocational",
    "Kombinierte berufliche Schule": "vocational",
    "Fachschule": "vocational",
    "Berufsfachschule": "vocational",
    "Berufsschule": "vocational",
    "Berufsschule mit sonderpäd. Aufgaben": "vocational",
    "Fachoberschule": "vocational",
    "Kombinierte allg./berufl. Schule": "vocational",
    "Volkshochschule": "adult",
    "Volkshochschul-Kolleg": "adult",
    "Kolleg": "adult",
    "Abend-Gymnasium": "adult",
}


class BuildError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


# --- geometry -------------------------------------------------------------------------


def _multipolygon(geometry: dict) -> list[list[list[tuple[float, float]]]]:
    if geometry["type"] == "Polygon":
        polys = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polys = geometry["coordinates"]
    else:
        raise BuildError(f"unexpected geometry {geometry['type']}")
    return [[simplify_ring(ring, AREA_TOLERANCE_M) for ring in poly] for poly in polys]


def _np_rings(mp: list) -> list[list[np.ndarray]]:
    return [[np.asarray(r, dtype=float) for r in poly] for poly in mp]


def _bbox(mp: list) -> tuple[float, float, float, float]:
    xs = [p[0] for poly in mp for p in poly[0]]
    ys = [p[1] for poly in mp for p in poly[0]]
    return min(xs), min(ys), max(xs), max(ys)


def _centroid(mp: list) -> tuple[float, float]:
    """Area-weighted centroid (lat, lng) of the outer rings."""
    sx = sy = sa = 0.0
    for poly in mp:
        ring = poly[0]
        for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
            c = x1 * y2 - x2 * y1
            sa += c
            sx += (x1 + x2) * c
            sy += (y1 + y2) * c
    if abs(sa) < 1e-15:
        x, y = mp[0][0][0]
        return y, x
    return sy / (3 * sa), sx / (3 * sa)


def _district_name(bez: str) -> str:
    return re.sub(r"^\d+\s*-\s*", "", bez).strip()


def _features(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


# --- steps ----------------------------------------------------------------------------


def build_areas(raw: Path) -> tuple[list[dict], list[dict]]:
    plr = []
    for f in _features(sources.verified_path("boundaries.lor_planning_areas_2021", raw)):
        p = f["properties"]
        plr.append(
            {
                "id": p["plr_id"],
                "name": p["plr_name"],
                "bzr_id": p["bzr_id"],
                "bzr_name": p["bzr_name"],
                "district": _district_name(p["bez"]),
                "polygons": _multipolygon(f["geometry"]),
            }
        )
    bzr = []
    for f in _features(sources.verified_path("boundaries.lor_district_regions_2021", raw)):
        p = f["properties"]
        bzr.append(
            {
                "id": p["bzr_id"],
                "name": p["bzr_name"],
                "district": _district_name(p["bez"]),
                "polygons": _multipolygon(f["geometry"]),
            }
        )
    if len(plr) != 542 or len(bzr) != 143:
        raise BuildError(f"expected 542 planning areas and 143 regions, got {len(plr)}/{len(bzr)}")
    for a in plr + bzr:
        a["lat"], a["lng"] = (round(v, 6) for v in _centroid(a["polygons"]))
    return plr, bzr


def assign_areas(lats: np.ndarray, lngs: np.ndarray, areas: list[dict]) -> np.ndarray:
    """Index into `areas` of the area containing each point (-1 = none)."""
    out = np.full(lats.shape, -1, dtype=np.int32)
    for i, a in enumerate(areas):
        x0, y0, x1, y1 = _bbox(a["polygons"])
        cand = np.nonzero((out < 0) & (lngs >= x0) & (lngs <= x1) & (lats >= y0) & (lats <= y1))[0]
        if cand.size == 0:
            continue
        inside = points_in_polygons(lngs[cand], lats[cand], _np_rings(a["polygons"]))
        out[cand[inside]] = i
    return out


def build_addresses(raw: Path, plr: list[dict]) -> tuple[list[tuple], dict]:
    path = sources.verified_path("living.rent_index_residential_location_2026", raw)
    log("  reading 120 MB of address points …")
    feats = _features(path)
    n = len(feats)
    lats = np.empty(n)
    lngs = np.empty(n)
    for i, f in enumerate(feats):
        lngs[i], lats[i] = f["geometry"]["coordinates"]
    log(f"  {n:,} addresses; assigning planning areas …")
    idx = assign_areas(lats, lngs, plr)

    # Points just outside every simplified outline (on borders, in the river): nearest
    # planning area with the register's planning-area name, else nearest centroid.
    by_name: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(plr):
        by_name[a["name"]].append(i)
    clat = np.array([a["lat"] for a in plr])
    clng = np.array([a["lng"] for a in plr])
    fallback = 0
    for k in np.nonzero(idx < 0)[0]:
        named = by_name.get(feats[k]["properties"].get("plr_name") or "", [])
        pool = named or list(range(len(plr)))
        d = haversine_m(lats[k], lngs[k], clat[pool], clng[pool])
        idx[k] = pool[int(np.argmin(d))]
        fallback += 1

    rows = []
    agree = 0
    classes: Counter = Counter()
    for k, f in enumerate(feats):
        p = f["properties"]
        wol = LOCATION_CLASS.get((p.get("wol") or "").strip())
        if wol is None:
            raise BuildError(
                f"address {p.get('schluessel')}: unknown location class {p.get('wol')!r}"
            )
        side = (p.get("stadtteil") or "").strip()
        if side not in ("Ost", "West"):
            raise BuildError(f"address {p.get('schluessel')}: East/West missing ({side!r})")
        area = plr[int(idx[k])]
        agree += area["name"] == p.get("plr_name")
        classes[wol] += 1
        street = p["strasse"].strip()
        hnr = clean_house_number(p["hnr"])
        rows.append(
            (
                street,
                hnr,
                p["plz"],
                p["bezname"],
                wol,
                "1" if side == "Ost" else "0",
                area["id"],
                f"{lats[k]:.6f}",
                f"{lngs[k]:.6f}",
                address_key(street, hnr),
            )
        )
    rows.sort(key=lambda r: (r[-1], r[2], r[3]))
    numbered = [(i + 1, *r) for i, r in enumerate(rows)]
    report = {
        "addresses": n,
        "location_classes": dict(classes),
        "planning_area_name_agreement": round(agree / n, 4),
        "assigned_by_fallback": fallback,
    }
    return numbered, report


def _norm_stop_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\s*\((berlin|bei berlin|b berlin)\)", "", n)
    n = re.sub(r"^(s\+u|s|u)\s+", "", n)
    n = n.replace("straße", "str.").replace("strasse", "str.")
    n = re.sub(r"\[.*?\]", "", n)
    n = re.sub(r"\s+(bhf|bahnhof)$", "", n)
    return re.sub(r"[^a-z0-9äöüß]", "", n)


def _vbb_modes() -> tuple[list[tuple[float, float, str, frozenset[str]]], bool]:
    """Timetable stations with the transport types that board there (empty if not built)."""
    d = sources.VBB_DIR
    if not all((d / f).is_file() for f in sources.VBB_FILES):
        return [], False
    with (d / "network_rides.csv").open(encoding="utf-8") as f:
        line_type = {r["line"]: r["route_type"] for r in csv.DictReader(f)}
    modes: dict[str, set[str]] = defaultdict(set)
    with (d / "network_boardings.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            mode = ROUTE_TYPES.get(line_type.get(r["line"], ""))
            if mode:
                modes[r["station"]].add(mode)
    stations = []
    with (d / "network_stations.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["station_id"] in modes:
                stations.append(
                    (float(r["lat"]), float(r["lng"]), r["name"], frozenset(modes[r["station_id"]]))
                )
    return stations, True


def build_stops(raw: Path) -> tuple[list[dict], dict]:
    feats = _features(sources.verified_path("mobility.bvg_stations", raw))
    groups: dict[str, list[dict]] = defaultdict(list)
    for f in feats:
        sid = f["properties"]["id"]
        if sid.startswith("de:11000:"):  # Berlin (AGS 11000)
            groups[":".join(sid.split(":")[:3])].append(f)
    vbb, have_vbb = _vbb_modes()
    vlat = np.array([s[0] for s in vbb]) if vbb else np.empty(0)
    vlng = np.array([s[1] for s in vbb]) if vbb else np.empty(0)
    vname = [_norm_stop_name(s[2]) for s in vbb]

    stops = []
    by_name = by_distance = 0
    for base, fs in sorted(groups.items()):
        main = next((f for f in fs if f["properties"]["id"] == base), None)
        main = main or max(fs, key=lambda f: f["properties"].get("weight") or 0)
        lng, lat = main["geometry"]["coordinates"]
        name = main["properties"]["name"].strip()
        modes: set[str] = set()
        if vbb:
            d = haversine_m(lat, lng, vlat, vlng)
            near = np.nonzero(d < 150)[0]
            key = _norm_stop_name(name)
            for j in near:
                if vname[j] == key:
                    modes |= vbb[j][3]
            if modes:
                by_name += 1
            else:
                for j in np.nonzero(d < 30)[0]:
                    modes |= vbb[j][3]
                by_distance += bool(modes)
        stops.append(
            {
                "id": base,
                "name": name,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "modes": sorted(modes),
            }
        )
    report = {
        "stops": len(stops),
        "vbb_timetable": have_vbb,
        "typed_by_name": by_name,
        "typed_by_distance": by_distance,
        "untyped": len(stops) - by_name - by_distance,
        "by_mode": dict(Counter(m for s in stops for m in s["modes"])),
    }
    return stops, report


def build_schools(raw: Path) -> list[dict]:
    out = []
    for f in _features(sources.verified_path("living.schools", raw)):
        p = f["properties"]
        lng, lat = f["geometry"]["coordinates"][:2]
        kind = SCHOOL_KIND.get(p["schulart"])
        if kind is None:
            kind = (
                "special" if p["schulart"].startswith(("Förderschwerp", "Übrige Förder")) else None
            )
        if kind is None:
            raise BuildError(f"unknown school type {p['schulart']!r}")
        out.append(
            {
                "name": p["schulname"].strip(),
                "kind": kind,
                "school_type": p["schulart"],
                "lat": round(lat, 6),
                "lng": round(lng, 6),
            }
        )
    return out


def build_kitas(raw: Path) -> tuple[list[dict], int]:
    from openpyxl import load_workbook

    wb = load_workbook(sources.verified_path("living.daycare_centers_2025-11", raw), read_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "Einrichtungsbezirk")
    header = list(rows[header_idx])
    col = {name: header.index(name) for name in header if name}
    out, skipped = [], 0
    for r in rows[header_idx + 1 :]:
        try:
            northing = float(str(r[col["ETRS_YKOORDINATE"]]).replace(",", "."))
            easting = float(str(r[col["ETRS_XKOORDINATE"]]).replace(",", "."))
        except (TypeError, ValueError):
            skipped += 1
            continue
        lat, lng = utm_to_latlng(easting, northing, zone=33)
        places = r[col["Erlaubte Plätze (BE)"]]
        out.append(
            {
                "name": str(r[col["Einrichtungsname"]]).strip(),
                "places": int(places) if isinstance(places, int | float) else None,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
            }
        )
    return out, skipped


def build_parks(raw: Path) -> list[dict]:
    out = []
    for f in _features(sources.verified_path("living.parks", raw)):
        p = f["properties"]
        area = float(p.get("katasterfl") or 0)
        if area < PARK_MIN_M2:
            continue
        mp = _multipolygon(f["geometry"])
        lat, lng = _centroid(mp)
        out.append(
            {
                "name": re.sub(r"\s+", " ", p.get("namenr") or "").strip() or "Green space",
                "area_m2": round(area),
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "polygons": mp,
            }
        )
    return out


def build_playgrounds(raw: Path) -> list[dict]:
    out = []
    for f in _features(sources.verified_path("living.playgrounds", raw)):
        p = f["properties"]
        lat, lng = _centroid(_multipolygon(f["geometry"]))
        out.append(
            {"name": (p.get("namenr") or "").strip(), "lat": round(lat, 6), "lng": round(lng, 6)}
        )
    return out


def build_air(raw: Path) -> dict:
    snap = json.loads(
        sources.verified_path("snapshots.air_quality_index_latest", raw).read_text(encoding="utf-8")
    )
    index = {
        s["station"]["code"].upper(): (s["data"].get("LQI_LQI"), s.get("datetime")) for s in snap
    }
    stations = []
    for f in _features(sources.verified_path("environment.air_quality_stations_luftdaten", raw)):
        p = f["properties"]
        if not p.get("active"):
            continue
        lng, lat = f["geometry"]["coordinates"][:2]
        lqi, when = index.get(p["code"].upper(), (None, None))
        stations.append(
            {
                "code": p["code"].upper(),
                "name": p["name"],
                "station_type": (p.get("stationgroups") or ["unknown"])[0],
                "lqi": int(lqi) if lqi is not None else None,
                "measured_at": when,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
            }
        )
    times = sorted({s["measured_at"] for s in stations if s["measured_at"]})
    return {"stations": stations, "snapshot": times[-1] if times else None}


def build_accidents(raw: Path) -> list[tuple]:
    path = sources.verified_path("mobility.traffic_accidents_2025_berlin", raw)
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            lat = float(r["YGCSWGS84"].replace(",", "."))
            lng = float(r["XGCSWGS84"].replace(",", "."))
            rows.append(
                (
                    f"{lat:.6f}",
                    f"{lng:.6f}",
                    int(r["UKATEGORIE"]),
                    int(r["IstRad"] == "1"),
                    int(r["IstFuss"] == "1"),
                )
            )
    return rows


def build_crime(raw: Path, bzr: list[dict]) -> dict:
    from data.neighborhoods.parse import CITY_KEY, read_crime_breakdown

    crime = read_crime_breakdown(sources.verified_path("society.crime_atlas_2016-2025", raw))
    missing = [r["id"] for r in bzr if r["id"] not in crime.rates]
    if missing:
        raise BuildError(f"no crime rate for district regions {missing}")
    for r in bzr:
        r["crime_rate"] = round(crime.rates[r["id"]]["kiez"], 1)
    return {"berlin_rate": round(crime.rates[CITY_KEY]["kiez"], 1), "years": list(crime.years)}


# --- planning-area typical values -----------------------------------------------------


def build_area_stats(build_dir: Path) -> dict:
    """Median of each measure over a sample of every planning area's addresses."""
    from berlin.local import LocalBerlinData
    from berlin.measures import AREA_MEASURES, measure_point

    data = LocalBerlinData(build_dir, with_area_stats=False)
    by_area: dict[str, list[int]] = defaultdict(list)
    for i, plr in enumerate(data.addr_plr):
        by_area[plr].append(i)
    stats: dict[str, dict[str, float]] = {}
    for area in data.planning_areas:
        members = by_area.get(area["id"], [])
        if members:
            step = max(1, len(members) // STATS_SAMPLE)
            points = [(float(data.addr_lat[i]), float(data.addr_lng[i])) for i in members[::step]]
            points = points[:STATS_SAMPLE]
        else:  # no residential address (parks, airports): measure at the centre
            points = [(area["lat"], area["lng"])]
        values: dict[str, list[float]] = defaultdict(list)
        for lat, lng in points:
            for key, value in measure_point(data, lat, lng).items():
                values[key].append(value)
        stats[area["id"]] = {
            key: round(statistics.median(vs), 1) for key, vs in values.items() if vs
        }
        stats[area["id"]]["addresses"] = len(members)
    return {"measures": list(AREA_MEASURES), "sample_per_area": STATS_SAMPLE, "areas": stats}


# --- main -----------------------------------------------------------------------------


def build(raw: Path, out: Path) -> dict:
    t0 = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    log(f"Raw files: {raw}")
    log("Checking checksums …")
    for s in sources.SOURCES:
        sources.verified_path(s.id, raw)
    report: dict = {}

    log("Mietspiegel table and checklist …")
    rows = read_rent_table(sources.verified_path("living.rent_index_table_2026", raw))
    files.write_json(
        files.RENT_TABLE, {"periods": PERIODS, "rows": [r.to_dict() for r in rows]}, out
    )
    items = read_checklist(sources.verified_path("living.rent_index_mietspiegel_2026", raw))
    files.write_json(files.CHECKLIST, [i.to_dict() for i in items], out)
    report["rent_rows"], report["checklist_items"] = len(rows), len(items)

    log("Planning areas, district regions and crime …")
    plr, bzr = build_areas(raw)
    crime = build_crime(raw, bzr)
    files.write_json(
        files.AREAS, {"planning_areas": plr, "district_regions": bzr, "crime": crime}, out
    )

    log("Addresses …")
    addresses, report["addresses"] = build_addresses(raw, plr)
    files.write_csv_gz(files.ADDRESSES, files.ADDRESS_COLUMNS, addresses, out)

    log("Stops …")
    stops, report["stops"] = build_stops(raw)
    files.write_json(files.STOPS, stops, out)

    log("Schools, Kitas, parks, playgrounds, air, accidents …")
    schools = build_schools(raw)
    kitas, kitas_skipped = build_kitas(raw)
    parks = build_parks(raw)
    playgrounds = build_playgrounds(raw)
    air = build_air(raw)
    accidents = build_accidents(raw)
    files.write_json(files.SCHOOLS, schools, out)
    files.write_json(files.KITAS, kitas, out)
    files.write_json(files.PARKS, parks, out)
    files.write_json(files.PLAYGROUNDS, playgrounds, out)
    files.write_json(files.AIR, air, out)
    files.write_csv_gz(files.ACCIDENTS, files.ACCIDENT_COLUMNS, accidents, out)
    report["counts"] = {
        "schools": len(schools),
        "kitas": len(kitas),
        "kitas_without_coordinates": kitas_skipped,
        "parks_1ha_plus": len(parks),
        "playgrounds": len(playgrounds),
        "air_stations": len(air["stations"]),
        "air_stations_with_index": sum(s["lqi"] is not None for s in air["stations"]),
        "accidents": len(accidents),
        "planning_areas": len(plr),
        "district_regions": len(bzr),
    }

    log("Typical values for the 542 planning areas (this takes a minute) …")
    files.write_json(files.AREA_STATS, build_area_stats(out), out)

    manifest = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "build_seconds": round(time.monotonic() - t0),
        "inputs": {s.id: s.sha256 for s in sources.SOURCES},
        "report": report,
    }
    files.write_json(files.MANIFEST, manifest, out)  # last: marks the build complete
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--raw", type=Path, default=None, help="Berlin Visualized data/raw folder")
    ap.add_argument("--out", type=Path, default=files.BUILD_DIR)
    args = ap.parse_args(argv)
    raw = args.raw or sources.raw_dir()
    try:
        manifest = build(raw, args.out)
    except (sources.SourceError, BuildError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    log(json.dumps(manifest["report"], indent=2, ensure_ascii=False))
    log(f"Done in {manifest['build_seconds']} s → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
