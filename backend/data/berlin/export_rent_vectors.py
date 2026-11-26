"""Write the rent-check test cases the browser implementation must reproduce.

    uv run python -m data.berlin.export_rent_vectors

The rent check for the user's own flat runs in the browser (ADR-0017), so there are two
implementations: berlin/rent.py (reference) and frontend/lib/rent/check.ts. This writes
`frontend/tests/fixtures/rent-vectors.json`: inputs and the reference results, on real
Mietspiegel rows. `tests/test_rent_vectors.py` fails if the file is stale; the frontend's
`tests/rent-check.test.ts` fails if the TypeScript disagrees with it.
"""

from __future__ import annotations

import json
from pathlib import Path

from berlin.checklist_en import LABELS, NOT_APPLICABLE
from berlin.rent import RentInput, check_rent
from data.berlin.mietspiegel import PERIODS

OUT = Path(__file__).resolve().parents[3] / "frontend" / "tests" / "fixtures" / "rent-vectors.json"

_GROUP = {"bath": 1, "kitchen": 2, "flat": 3, "building": 4, "surroundings": 5}
CHECKLIST = [
    {
        "id": i,
        "group": _GROUP[i.split("-")[0]],
        "sign": "+" if "-plus-" in i else "-",
        "not_applicable": sorted(NOT_APPLICABLE.get(i, set())),
    }
    for i in LABELS
]
# Real rows from the Mietspiegeltabelle 2026.
ROWS = [
    {
        "row": 3,
        "location": "simple",
        "period": "pre1918",
        "size_min": 40,
        "size_max": 45,
        "low": 7.01,
        "mean": 9.27,
        "high": 12.25,
    },
    {
        "row": 24,
        "location": "simple",
        "period": "1965-1972",
        "size_min": 40,
        "size_max": 55,
        "low": 6.23,
        "mean": 7.32,
        "high": 9.53,
    },
    {
        "row": 78,
        "location": "medium",
        "period": "1919-1949",
        "size_min": 0,
        "size_max": 40,
        "low": 7.74,
        "mean": 8.83,
        "high": 10.51,
    },
    {
        "row": 81,
        "location": "medium",
        "period": "1919-1949",
        "size_min": 60,
        "size_max": None,
        "low": 5.90,
        "mean": 7.30,
        "high": 9.55,
    },
    {
        "row": 91,
        "location": "medium",
        "period": "1973-1985-west",
        "size_min": 35,
        "size_max": 40,
        "low": 6.60,
        "mean": 7.78,
        "high": 10.49,
    },
    {
        "row": 103,
        "location": "medium",
        "period": "1973-1990-east",
        "size_min": 0,
        "size_max": 40,
        "low": 6.63,
        "mean": 7.64,
        "high": 9.84,
    },
    {
        "row": 124,
        "location": "medium",
        "period": "2016-2019",
        "size_min": 70,
        "size_max": 95,
        "low": 10.24,
        "mean": 14.42,
        "high": 17.68,
    },
    {
        "row": 135,
        "location": "good",
        "period": "pre1918",
        "size_min": 60,
        "size_max": 70,
        "low": 7.09,
        "mean": 9.46,
        "high": 13.54,
    },
    {
        "row": 172,
        "location": "good",
        "period": "1991-2001",
        "size_min": 65,
        "size_max": 75,
        "low": 7.52,
        "mean": 11.06,
        "high": 13.21,
    },
]

CASES = [
    (
        "brochure example 10.4 B",
        dict(
            location_class="medium",
            east=False,
            year_built=1930,
            size_m2=60,
            cold_rent_eur=465,
            features=[
                "bath-plus-01",
                "kitchen-plus-03",
                "flat-plus-01",
                "building-minus-01",
                "surroundings-minus-01",
            ],
        ),
    ),
    (
        "index only, within",
        dict(location_class="good", east=True, year_built=1908, size_m2=61, cold_rent_eur=600),
    ),
    (
        "index only, above",
        dict(location_class="good", east=True, year_built=1908, size_m2=61, cold_rent_eur=860),
    ),
    (
        "below the index",
        dict(location_class="simple", east=False, year_built=1900, size_m2=44, cold_rent_eur=250),
    ),
    (
        "energy 160 + net plus",
        dict(
            location_class="simple",
            east=True,
            year_built=1965,
            size_m2=44,
            cold_rent_eur=520,
            energy_kwh=160,
            features=[
                "bath-plus-04",
                "bath-plus-11",
                "kitchen-plus-03",
                "kitchen-plus-05",
                "flat-plus-01",
                "flat-minus-07",
                "building-minus-02",
            ],
        ),
    ),
    (
        "energy replaces insulation",
        dict(
            location_class="medium",
            east=False,
            year_built=1930,
            size_m2=60,
            features=["building-plus-08"],
            energy_kwh=240,
        ),
    ),
    (
        "demand value, no hot water",
        dict(
            location_class="medium",
            east=False,
            year_built=1930,
            size_m2=60,
            energy_kwh=110,
            energy_is_demand=True,
            energy_without_hot_water=True,
        ),
    ),
    (
        "all groups down",
        dict(
            location_class="medium",
            east=False,
            year_built=1930,
            size_m2=60,
            features=[f"{g}-minus-01" for g in _GROUP],
        ),
    ),
    (
        "ignored for building age",
        dict(
            location_class="medium",
            east=False,
            year_built=2017,
            size_m2=80,
            features=["bath-plus-07", "bath-plus-01"],
            cold_rent_eur=1200,
        ),
    ),
    (
        "new build",
        dict(location_class="medium", east=False, year_built=2017, size_m2=80, cold_rent_eur=1600),
    ),
    (
        "after 2024",
        dict(location_class="medium", east=False, year_built=2025, size_m2=80, cold_rent_eur=1600),
    ),
    (
        "east 1980",
        dict(location_class="medium", east=True, year_built=1980, size_m2=38, cold_rent_eur=300),
    ),
    (
        "west 1980",
        dict(location_class="medium", east=False, year_built=1980, size_m2=38, cold_rent_eur=300),
    ),
    (
        "1949 without heating",
        dict(
            location_class="medium",
            east=False,
            year_built=1930,
            size_m2=60,
            no_central_heating_or_bath=True,
            cold_rent_eur=480,
        ),
    ),
    (
        "tie in a group",
        dict(
            location_class="good",
            east=False,
            year_built=1995,
            size_m2=70,
            features=["bath-plus-01", "bath-minus-01", "kitchen-plus-02"],
            cold_rent_eur=780,
        ),
    ),
]

_KEEP = (
    "covered",
    "period",
    "low",
    "mean",
    "high",
    "net_groups",
    "used_checklist",
    "comparable",
    "limit",
    "exempt",
    "asked",
    "verdict",
    "over_per_m2",
    "over_per_month",
    "ignored_features",
)


def build() -> dict:
    vectors = []
    for name, kw in CASES:
        kw = dict(kw)
        kw["features"] = frozenset(kw.get("features", []))
        result = check_rent(RentInput(**kw), ROWS, PERIODS, CHECKLIST).to_dict()
        expected = {k: result[k] for k in _KEEP}
        expected["row"] = result["row"]["row"] if result["row"] else None
        expected["groups"] = [g["effect"] for g in result["groups"]]
        vectors.append(
            {
                "name": name,
                "input": {**kw, "features": sorted(kw["features"])},
                "expected": expected,
            }
        )
    return {"rows": ROWS, "periods": PERIODS, "checklist": CHECKLIST, "vectors": vectors}


def dump(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dump(build()), encoding="utf-8")
    print(f"{len(CASES)} rent vectors → {OUT}")
