"""Build the Berlin Neighbourhoods bundle (`make neighborhoods-data`).

Reads the official files in data/neighborhoods/raw/ (see raw/README.md) plus the shipped
Lifestyle Match bundle (data/lifestyle/regions.json: names, population, amenities,
environment, transit, rents, commute times) and writes data/neighborhoods/neighborhoods.json:

    regions[]      143 LOR Bezirksregionen: name, district, wider area, population,
                   centre, and for every metric {raw, source_id, year, method}
    references     per metric: the Berlin-wide figure and the sorted distribution of all
                   143 regional values — the fixed yardstick scores are read against
    sources        every publication a number comes from
    inputs         SHA-256 of every input file

Deterministic: same inputs → byte-identical output (sorted keys, rounded values, no
timestamps). `make test-all` rebuilds and compares when the raw files are present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from data.lifestyle import geo
from data.neighborhoods import sources as S
from data.neighborhoods.measure import (
    FACILITIES,
    PARKING_AREA_RADIUS_M,
    PARKING_METER_RADIUS_M,
    RegionAccess,
    RegionLandValue,
    RegionRoads,
    home_samples,
    land_values,
    measure_access,
    measure_roads,
)
from data.neighborhoods.parse import (
    CITY_KEY,
    BzrMeta,
    CrimeRates,
    IncomeReport,
    MssRow,
    ParseError,
    SchoolTables,
    read_accidents,
    read_bzr_meta,
    read_crime_breakdown,
    read_income_report,
    read_land_zones,
    read_mss_pdf,
    read_school_pdf,
)
from neighborhoods.catalog import METRICS, METRICS_BY_ID

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
BUNDLE_PATH = HERE / "neighborhoods.json"
LIFESTYLE_BUNDLE = HERE.parent / "lifestyle" / "regions.json"
SHAPES = HERE.parent / "lifestyle" / "regions_geo.json"
SCHEMA_VERSION = 1

CRIME_GLOB = "fallzahlen_hz-*.xlsx"
MSS_GLOB = "*mss2023*.pdf"
SCHOOL_GLOB = "Blickpunkt_Schule*.pdf"
ACCIDENT_GLOB = "Unfallorte*_CSV.zip"
OSM_GLOB = "berlin-*free.gpkg.zip"
BZR_CSV_GLOB = "lor_2021_b_lor_bzr_2021_*.csv"
BZR_GEOJSON_GLOB = "lor_2021_b_lor_bzr_2021_*.geojson"
LAND_GLOB = "brw*_vector_*.geojson"
# The report itself, not its metadata document ("Lohn- und Einkommensteuer im Land Berlin.pdf").
INCOME_GLOB = "Statistischer Bericht*Einkommensteuer*.pdf"

CENTRE_DESTINATION = "alexanderplatz"
MAX_SHAPE_AREA_DEVIATION = 0.02  # simplified outlines vs. the official areas

CRIME_METRICS = {  # our metric id -> parse.CRIME_COLUMNS id
    "crime_kiez": "kiez",
    "crime_violence": "violence",
    "crime_robbery": "robbery",
    "crime_burglary": "burglary",
    "crime_total": "total",
    "crime_bike_theft": "bike_theft",
    "crime_car": "car_crime",
}
LIFESTYLE_METRICS = {  # our metric id -> Lifestyle Match measure id
    "cafes": "cafes",
    "everyday": "everyday",
    "culture": "culture",
    "sport": "sport",
    "nightlife": "nightlife",
    "green_supply": "green",
    "water_forest": "water",
    "rail_distance": "transit",
    "quiet": "quiet",
    "clean_air": "clean_air",
    "cool_summer": "cool_summer",
}
ACCESS_COUNTS = {  # our metric id -> measure.FACILITIES id
    "doctors": "doctors",
    "pharmacies": "pharmacies",
    "schools": "schools",
    "kitas": "kitas",
    "playgrounds": "playgrounds",
    "stops": "stops",
}
DECIMALS = {"int": 1, "dec1": 2, "dec2": 3, "pct": 1, "metres": 0, "minutes": 0, "eur_m2": 2}
STATUS_SHARE_NAMES = {1: "high", 2: "middle", 3: "low", 4: "very_low"}


class BuildError(RuntimeError):
    pass


def _round(metric_id: str, value: float) -> float:
    return round(float(value), DECIMALS.get(METRICS_BY_ID[metric_id].fmt, 2))


def weighted_mean(pairs: Iterable[tuple[float, float]]) -> float:
    """Σ w·v / Σ w over (value, weight) pairs with positive weight."""
    pairs = [(v, w) for v, w in pairs if w > 0]
    total = sum(w for _, w in pairs)
    if total <= 0:
        raise BuildError("no weight to average over")
    return sum(v * w for v, w in pairs) / total


def status_by_region(rows: Iterable[MssRow]) -> dict[str, tuple[float, dict[str, float], int]]:
    """Region -> (resident-weighted mean status class, % residents per class, residents).

    Planning areas the Senate didn't index (status None) are left out of the average.
    """
    groups: dict[str, list[MssRow]] = {}
    for r in rows:
        if r.status is not None and r.population > 0:
            groups.setdefault(r.region_key, []).append(r)
    out = {}
    for key, items in groups.items():
        pop = sum(r.population for r in items)
        mean = sum(r.status * r.population for r in items) / pop
        shares = {
            name: round(100 * sum(r.population for r in items if r.status == cls) / pop, 1)
            for cls, name in STATUS_SHARE_NAMES.items()
        }
        out[key] = (mean, shares, pop)
    return out


def _value(metric_id: str, raw: float, source_id: str, year: str, method: str, **extra) -> dict:
    v = {
        "raw": _round(metric_id, raw),
        "source_id": source_id,
        "year": year,
        "method": method,
    }
    v.update({k: x for k, x in extra.items() if x is not None})
    return v


def build_bundle(
    *,
    lifestyle: dict,
    bzr: Mapping[str, BzrMeta],
    crime: CrimeRates,
    mss: list[MssRow],
    schools: SchoolTables,
    access: Mapping[str, RegionAccess],
    roads: Mapping[str, RegionRoads],
    accident_year: int,
    land: Mapping[str, RegionLandValue],
    land_date: str,
    income: IncomeReport,
    inputs: Mapping[str, str],
) -> dict:
    """Assemble the bundle from parsed inputs (pure; no file access)."""
    ls_regions = {r["key"]: r for r in lifestyle["regions"]}
    keys = sorted(ls_regions)
    if set(keys) != set(bzr):
        raise BuildError("Lifestyle regions and LOR Bezirksregionen differ")
    status = status_by_region(mss)
    crime_years = f"{crime.years[0]}–{crime.years[-1]}"
    commute = lifestyle["commute"]["times"][CENTRE_DESTINATION]
    ls_sources = lifestyle["sources"]

    regions = []
    for key in keys:
        ls = ls_regions[key]
        meta = bzr[key]
        # Display names come from the Lifestyle bundle, which disambiguates a few official
        # ones ("Heerstraße" ×2, "MV Nord" → "Märkisches Viertel Nord"); so do both features.
        if ls["district"] != meta.district:
            raise BuildError(f"{key}: district differs between LOR and Lifestyle bundle")
        values: dict[str, dict] = {}

        # Safety — Kriminalitätsatlas
        if key not in crime.rates:
            raise BuildError(f"{key}: no crime rates")
        for mid, cid in CRIME_METRICS.items():
            values[mid] = _value(
                mid,
                crime.rates[key][cid],
                S.PKS,
                crime_years,
                f"Mean Häufigkeitszahl {crime_years} (offences per 100,000 residents).",
            )
        kiez_ls = ls["measures"]["safety"]["raw"]
        if abs(values["crime_kiez"]["raw"] - kiez_ls) > 0.11:
            raise BuildError(f"{key}: Kieztaten {values['crime_kiez']['raw']} != {kiez_ls}")

        # Road safety — Unfallatlas + OSM streets
        rd = roads.get(key)
        if rd is None or rd.street_km <= 0:
            raise BuildError(f"{key}: no street network measured")
        per10 = 10 / rd.street_km
        road_method = (
            f"{{n}} {{what}} in {accident_year} ÷ {rd.street_km:.1f} km of public street "
            "in the area (OSM), × 10."
        )
        for mid, n, what in (
            ("accidents", rd.accidents, "injury accidents"),
            ("accidents_severe", rd.severe, "accidents with someone killed or seriously injured"),
            (
                "accidents_vulnerable",
                rd.vulnerable,
                "injury accidents involving a pedestrian or " "cyclist",
            ),
        ):
            values[mid] = _value(
                mid,
                n * per10,
                S.UNFALLATLAS,
                str(accident_year),
                road_method.format(n=n, what=what),
                count=n,
            )

        # Affluence — MSS status index
        if key not in status:
            raise BuildError(f"{key}: no indexed planning area in the MSS")
        mean, shares, pop = status[key]
        values["social_status"] = _value(
            "social_status",
            mean,
            S.MSS,
            "2022",
            f"Status class of the area's indexed planning areas, weighted by their "
            f"{pop:,} residents (31 Dec 2022).",
            shares=shares,
        )

        # Education — district school figures + OSM access
        d = meta.district
        school_year = "2024/25"
        values["edu_abitur"] = _value(
            "edu_abitur",
            schools.share(d, "abitur"),
            S.SCHOOLS,
            school_year,
            f"{schools.leavers[d]['abitur']:,} of {sum(schools.leavers[d].values()):,} leavers "
            f"from general schools in {d} (Abb. 5.1.2).",
        )
        values["edu_no_qualification"] = _value(
            "edu_no_qualification",
            schools.share(d, "none"),
            S.SCHOOLS,
            school_year,
            f"{schools.leavers[d]['none']:,} of {sum(schools.leavers[d].values()):,} leavers "
            f"from general schools in {d} left without the Berufsbildungsreife (Abb. 5.1.2).",
        )
        values["edu_gymnasium"] = _value(
            "edu_gymnasium",
            schools.gymnasium_pct[d],
            S.SCHOOLS,
            school_year,
            f"Share of primary pupils in {d} with a Gymnasium/ISS recommendation (Tab. 3.2.3).",
        )

        # OSM access from homes
        acc = access[key]
        homes = (
            f"Mean over {acc.homes} home sample points (100 m grid on residential land)"
            if acc.homes
            else "Measured from the area's residential centre (no mapped residential land)"
        )
        for mid, fid in ACCESS_COUNTS.items():
            fac = FACILITIES[fid]
            values[mid] = _value(
                mid,
                acc.counts[fid],
                S.OSM_NEW,
                "2026",
                f"{homes}: {fac.label} within {fac.radius_m:,} m, straight line.",
            )
        values["hospital_distance"] = _value(
            "hospital_distance",
            acc.hospital_m,
            S.OSM_NEW,
            "2026",
            f"{homes}: straight-line distance to the nearest hospital.",
        )
        values["park_distance"] = _value(
            "park_distance",
            acc.park_m,
            S.OSM_NEW,
            "2026",
            f"{homes}: distance to the edge of the nearest park ≥ 1 ha (capped at 3 km).",
        )
        values["paid_parking"] = _value(
            "paid_parking",
            acc.paid_parking_share,
            S.OSM_NEW,
            "2026",
            f"{homes}: share with a parking ticket machine within {PARKING_METER_RADIUS_M} m.",
        )
        values["parking_area"] = _value(
            "parking_area",
            acc.parking_area_m2,
            S.OSM_NEW,
            "2026",
            f"{homes}: area of mapped car parks (centre within {PARKING_AREA_RADIUS_M} m).",
        )

        # Affluence — Bodenrichtwerte at homes
        lv = land.get(key)
        if lv is None:
            raise BuildError(f"{key}: no home point lies in a residential land-value zone")
        land_year = land_date[:4]
        cover = f"{lv.homes} of {lv.homes_total} home sample points lie in residential zones"
        values["land_value"] = _value(
            "land_value",
            lv.index,
            S.LAND_VALUES,
            land_year,
            f"Mean percentile of the Bodenrichtwerte ({land_date}) at the area's homes among "
            f"Berlin's residential zones of the same kind (houses vs. flats); {cover}, "
            f"{lv.houses_share:.0f}% of them in zones for houses.",
        )
        values["land_value_eur"] = _value(
            "land_value_eur",
            lv.median_eur,
            S.LAND_VALUES,
            land_year,
            f"Median Bodenrichtwert ({land_date}) over the area's homes; {cover}.",
        )

        # Reused Lifestyle Match figures
        for mid, attr in LIFESTYLE_METRICS.items():
            m = ls["measures"][attr]
            values[mid] = _value(
                mid, m["raw"], m["source_id"], m["year"], m["method"], shares=m.get("shares")
            )
        t = commute[key]
        values["commute_centre"] = _value(
            "commute_centre",
            t["minutes"],
            lifestyle["commute"]["source_id"],
            "2026",
            lifestyle["commute"]["method"]
            + ("" if t["source"] == "network" else " (straight-line estimate for this area)"),
        )
        values["density"] = _value(
            "density",
            ls["density_per_km2"],
            ls["geo_source_id"],
            "2024",
            f"{ls['population']:,} registered residents (31 Dec 2024) ÷ {ls['area_km2']} km².",
        )
        values["rent"] = _value(
            "rent",
            ls["rent"]["raw"],
            ls["rent"]["source_id"],
            ls["rent"]["year"],
            ls["rent"]["method"],
        )

        regions.append(
            {
                "key": key,
                "name": ls["name"],
                "district": meta.district,
                "area_group": meta.area_group,
                "population": ls["population"],
                "centroid": ls["centroid"],
                "area_km2": ls["area_km2"],
                "rent_range": ls["rent_range"],
                "values": values,
            }
        )

    references = _references(
        regions, lifestyle, crime, status, schools, roads, access, accident_year
    )
    median = income.median_bracket()
    city = {
        "income_per_taxpayer": {
            "value": round(income.mean_eur),
            "unit": "EUR per taxpayer per year (total income)",
            "source_id": S.INCOME_TAX,
            "year": str(income.year),
            "note": f"Berlin as a whole: €{income.income_keur / 1e6:.1f} billion total income "
            f"of {income.taxpayers:,} taxpayers with positive income; the median taxpayer is in "
            f"the €{median.low:,}–{median.high:,} bracket. The report has no district breakdown.",
        }
    }
    sources = {sid: ls_sources[sid] for sid in S.REUSED} | S.SOURCES
    used = {v["source_id"] for r in regions for v in r["values"].values()}
    used |= {fig["source_id"] for fig in city.values()}
    missing = used - set(sources)
    if missing:
        raise BuildError(f"values cite unregistered sources: {sorted(missing)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "inputs": dict(sorted(inputs.items())),
        "sources": {sid: sources[sid] for sid in sorted(used)},
        "city": city,
        "references": references,
        "regions": regions,
    }


def _references(regions, lifestyle, crime, status, schools, roads, access, accident_year):
    pop = {r["key"]: r["population"] for r in regions}
    ls_refs = lifestyle["references"]
    berlin: dict[str, tuple[float, str]] = {}
    for mid, cid in CRIME_METRICS.items():
        berlin[mid] = (crime.rates[CITY_KEY][cid], "Berlin-wide rate (PKS total)")
    street_km = sum(r.street_km for r in roads.values())
    for mid, attr in (
        ("accidents", "accidents"),
        ("accidents_severe", "severe"),
        ("accidents_vulnerable", "vulnerable"),
    ):
        n = sum(getattr(r, attr) for r in roads.values())
        berlin[mid] = (
            10 * n / street_km,
            f"All of Berlin: {n:,} in {accident_year} over " f"{street_km:,.0f} km of street",
        )
    total_pop = sum(p for _, _, p in status.values())
    berlin["social_status"] = (
        sum(m * p for m, _, p in status.values()) / total_pop,
        "Berlin, weighted by residents of indexed planning areas",
    )
    berlin["edu_abitur"] = (schools.share_berlin("abitur"), "All Berlin districts")
    berlin["edu_no_qualification"] = (schools.share_berlin("none"), "All Berlin districts")
    berlin["edu_gymnasium"] = (schools.gymnasium_pct_berlin, "Berlin (Tab. 3.2.3)")
    weighted = "Mean of all areas, weighted by residents"
    for mid in (
        *ACCESS_COUNTS,
        "land_value",
        "land_value_eur",
        "hospital_distance",
        "park_distance",
        "paid_parking",
        "parking_area",
        "commute_centre",
    ):
        berlin[mid] = (
            weighted_mean((r["values"][mid]["raw"], pop[r["key"]]) for r in regions),
            weighted,
        )
    for mid, attr in LIFESTYLE_METRICS.items():
        berlin[mid] = (ls_refs[attr]["berlin"], "Berlin-wide figure (Lifestyle Match bundle)")
    area = sum(r["area_km2"] for r in regions)
    berlin["density"] = (sum(pop.values()) / area, "Berlin: residents ÷ area")
    berlin["rent"] = (
        lifestyle["city"]["asking_rent_median"]["value"],
        "Berlin median asking rent (IBB Wohnungsmarktbericht 2025)",
    )

    out = {}
    for m in METRICS:
        vals = [r["values"][m.id]["raw"] for r in regions if m.id in r["values"]]
        if not vals:
            continue  # pending metric
        if len(vals) != len(regions):
            raise BuildError(f"{m.id}: only {len(vals)} of {len(regions)} regions have data")
        b, how = berlin[m.id]
        out[m.id] = {
            "berlin": _round(m.id, b),
            "berlin_method": how,
            "distribution": sorted(vals),
        }
    return out


# --- Files ------------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_one(raw_dir: Path, pattern: str) -> Path:
    matches = sorted(raw_dir.glob(pattern))
    if not matches:
        raise BuildError(f"No file matching {pattern!r} in {raw_dir} (see raw/README.md)")
    return matches[-1]


def load_region_polygons(path: Path = SHAPES) -> dict[str, list]:
    shapes = json.loads(path.read_text(encoding="utf-8"))
    return {f["properties"]["key"]: geo.geojson_polygons(f["geometry"]) for f in shapes["features"]}


def check_outlines(polygons: Mapping[str, list], official_geojson: Path) -> float:
    """Largest relative area difference between the shipped outlines and the official LOR."""
    official = json.loads(official_geojson.read_text(encoding="utf-8"))
    worst = 0.0
    for f in official["features"]:
        key = f["properties"]["bzr_id"]
        if key not in polygons:
            raise BuildError(f"official Bezirksregion {key} missing from the outlines")
        expected = float(f["properties"]["finhalt"])
        got, _ = geo.polygons_area_centroid(polygons[key])
        worst = max(worst, abs(got - expected) / expected)
    if len(official["features"]) != len(polygons):
        raise BuildError("outline count differs from the official Bezirksregionen")
    if worst > MAX_SHAPE_AREA_DEVIATION:
        raise BuildError(f"outlines deviate {worst:.1%} from the official areas")
    return worst


def build_from_files(raw_dir: Path = RAW_DIR, lifestyle_path: Path = LIFESTYLE_BUNDLE) -> dict:
    paths = {
        "crime": _find_one(raw_dir, CRIME_GLOB),
        "mss": _find_one(raw_dir, MSS_GLOB),
        "schools": _find_one(raw_dir, SCHOOL_GLOB),
        "accidents": _find_one(raw_dir, ACCIDENT_GLOB),
        "osm": _find_one(raw_dir, OSM_GLOB),
        "bzr_csv": _find_one(raw_dir, BZR_CSV_GLOB),
        "bzr_geojson": _find_one(raw_dir, BZR_GEOJSON_GLOB),
        "land": _find_one(raw_dir, LAND_GLOB),
        "income": _find_one(raw_dir, INCOME_GLOB),
    }
    lifestyle = json.loads(lifestyle_path.read_text(encoding="utf-8"))
    polygons = load_region_polygons()
    deviation = check_outlines(polygons, paths["bzr_geojson"])
    print(f"✓ outlines match the official LOR areas (max deviation {deviation:.2%})")

    bzr = read_bzr_meta(paths["bzr_csv"])
    crime = read_crime_breakdown(paths["crime"])
    mss = read_mss_pdf(paths["mss"])
    schools = read_school_pdf(paths["schools"])
    accidents, year = read_accidents(paths["accidents"])
    zones, land_date = read_land_zones(paths["land"])
    income = read_income_report(paths["income"])
    print(
        f"✓ parsed: {len(zones)} residential land-value zones ({land_date}); income-tax "
        f"statistics {income.year}: {income.taxpayers:,} taxpayers, "
        f"€{income.mean_eur:,.0f} mean total income"
    )
    print(
        f"✓ parsed: {len(crime.rates)} crime rows, {len(mss)} planning areas, "
        f"{len(accidents):,} accidents ({year}), 12 districts' school figures"
    )

    centres = {r["key"]: tuple(r["centroid"]) for r in lifestyle["regions"]}
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(paths["osm"]) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".gpkg"))
        gpkg = Path(zf.extract(name, tmp))
        print("… measuring from homes (about a minute)")
        samples = home_samples(gpkg, polygons)
        access = measure_access(gpkg, polygons, centres, samples)
        land = land_values(samples, zones)
        roads = measure_roads(gpkg, polygons, accidents)
    assigned = sum(r.accidents for r in roads.values())
    if assigned < 0.99 * len(accidents):
        raise BuildError(f"only {assigned} of {len(accidents)} accidents fall inside Berlin")

    inputs = {p.name: _sha256(p) for p in paths.values()}
    inputs[lifestyle_path.name] = _sha256(lifestyle_path)
    return build_bundle(
        lifestyle=lifestyle,
        bzr=bzr,
        crime=crime,
        mss=mss,
        schools=schools,
        access=access,
        roads=roads,
        accident_year=year,
        land=land,
        land_date=land_date,
        income=income,
        inputs=inputs,
    )


def dump(bundle: dict) -> str:
    return json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--out", type=Path, default=BUNDLE_PATH)
    args = parser.parse_args(argv)
    try:
        bundle = build_from_files(args.raw_dir)
    except (BuildError, ParseError) as exc:
        raise SystemExit(f"✗ {exc}") from None
    args.out.write_text(dump(bundle), encoding="utf-8")
    n = len(bundle["regions"])
    print(f"✓ wrote {args.out.name}: {n} areas, {len(bundle['references'])} metrics")


if __name__ == "__main__":
    main()
