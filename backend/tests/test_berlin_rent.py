"""Rent check maths (ADR-0017): pure, no data files needed."""

from __future__ import annotations

import pytest

from berlin.checklist_en import LABELS, NOT_APPLICABLE
from berlin.rent import (
    RentInput,
    check_rent,
    energy_features,
    explain,
    find_row,
    period_for,
    rent_by_period,
)
from data.berlin.mietspiegel import PERIODS

_GROUP = {"bath": 1, "kitchen": 2, "flat": 3, "building": 4, "surroundings": 5}
CHECKLIST = [
    {"id": i, "group": _GROUP[i.split("-")[0]], "sign": "+" if "-plus-" in i else "-"}
    for i in LABELS
]

# Real rows from the Mietspiegeltabelle 2026 (medium location).
ROWS = [
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
        "row": 124,
        "location": "medium",
        "period": "2016-2019",
        "size_min": 70,
        "size_max": 95,
        "low": 10.24,
        "mean": 14.42,
        "high": 17.68,
    },
]


def check(**kw):
    base = {"location_class": "medium", "east": False, "year_built": 1930, "size_m2": 60}
    return check_rent(RentInput(**{**base, **kw}), ROWS, PERIODS, CHECKLIST)


def test_brochure_example_10_4_b():
    # Mietspiegel No. 10.4 B: groups 1–3 raise, 4–5 lower → net +1 → +20 % of the upper
    # span: 7.30 + 0.2 × (9.55 − 7.30) = 7.75 €/m².
    features = frozenset(
        {
            "bath-plus-01",
            "kitchen-plus-03",
            "flat-plus-01",
            "building-minus-01",
            "surroundings-minus-01",
        }
    )
    r = check(features=features)
    assert r.row["row"] == 81
    assert [g.effect for g in r.groups] == [1, 1, 1, -1, -1]
    assert r.net_groups == 1
    assert r.comparable == 7.75
    assert r.limit == pytest.approx(8.53)


def test_net_minus_uses_the_lower_span():
    r = check(features=frozenset({"bath-minus-01", "kitchen-minus-01"}))
    assert r.comparable == pytest.approx(7.30 - 0.4 * (7.30 - 5.90))


def test_majority_inside_a_group_and_ties():
    two_one = check(features=frozenset({"bath-plus-01", "bath-plus-02", "bath-minus-01"}))
    assert two_one.groups[0].effect == 1
    tie = check(features=frozenset({"bath-plus-01", "bath-minus-01"}))
    assert tie.groups[0].effect == 0 and tie.comparable == 7.30


def test_all_five_groups_reach_the_range_edges():
    up = check(features=frozenset({f"{g}-plus-01" for g in _GROUP}))
    down = check(features=frozenset({f"{g}-minus-01" for g in _GROUP}))
    assert up.comparable == 9.55 and down.comparable == 5.90


def test_without_checklist_the_limit_is_mean_plus_ten_percent():
    r = check()
    assert r.comparable == 7.30 and r.limit == 8.03 and not r.used_checklist


@pytest.mark.parametrize(
    "cold,verdict",
    [
        (60 * 5.50, "below_index"),
        (60 * 7.00, "within_limit"),
        (60 * 8.03, "within_limit"),
        (60 * 9.00, "above_limit"),
    ],
)
def test_verdicts(cold, verdict):
    assert check(cold_rent_eur=cold).verdict == verdict


def test_over_the_limit_amounts():
    r = check(cold_rent_eur=60 * 9.03)
    assert r.over_per_m2 == 1.00 and r.over_per_month == 60


def test_new_build_has_no_limit():
    r = check_rent(
        RentInput("medium", False, 2017, 80, cold_rent_eur=80 * 20), ROWS, PERIODS, CHECKLIST
    )
    assert r.row["row"] == 124 and r.exempt == "new_build" and r.limit is None
    assert r.verdict == "new_build"


def test_after_2024_is_not_covered():
    r = check(year_built=2025, cold_rent_eur=1000)
    assert not r.covered and r.verdict == "not_covered"


def test_east_west_periods():
    assert period_for(1980, True, PERIODS) == "1973-1990-east"
    assert period_for(1980, False, PERIODS) == "1973-1985-west"
    assert period_for(1988, False, PERIODS) == "1986-1990-west"
    assert period_for(1900, True, PERIODS) == "pre1918"
    assert period_for(2025, False, PERIODS) is None


def test_size_bands_are_lower_inclusive():
    assert find_row(ROWS, "medium", "1919-1949", 39.9)["row"] == 78
    assert find_row(ROWS, "medium", "1919-1949", 60)["row"] == 81
    assert find_row(ROWS, "medium", "1919-1949", 250)["row"] == 81


def test_energy_boxes():
    # Brochure No. 10.4 A: 240 kWh ticks all three lowering boxes, 90 kWh the two upper
    # raising boxes.
    assert energy_features(240) == {
        "building-minus-energy-145",
        "building-minus-energy-195",
        "building-minus-energy-235",
    }
    assert energy_features(90) == {"building-plus-energy-120", "building-plus-energy-100"}
    # Demand values: limits 20 % higher. Without hot water: +20 kWh first.
    assert energy_features(170, is_demand=True) == set()
    assert energy_features(130, without_hot_water=True) == {"building-minus-energy-145"}


def test_energy_value_replaces_the_insulation_item():
    r = check(features=frozenset({"building-plus-08"}), energy_kwh=240)
    assert r.groups[3].plus == 0 and r.groups[3].minus == 3 and r.groups[3].effect == -1


def test_items_that_dont_apply_to_the_building_age_are_ignored():
    r = check_rent(
        RentInput("medium", False, 2017, 80, features=frozenset({"bath-plus-07"})),
        ROWS,
        PERIODS,
        CHECKLIST,
    )
    assert r.ignored_features == ["bath-plus-07"] and r.groups[0].effect == 0


def test_pre_1949_without_heating_or_bath_deduction():
    r = check(no_central_heating_or_bath=True)
    assert (r.low, r.mean, r.high) == (5.57, 6.97, 9.22)
    modern = check_rent(
        RentInput("medium", False, 2017, 80, no_central_heating_or_bath=True),
        ROWS,
        PERIODS,
        CHECKLIST,
    )
    assert modern.mean == 14.42  # only flats ready by 1949


def test_mean_by_period_for_the_chart():
    bars = rent_by_period(ROWS, "medium", False, 38, PERIODS)
    assert [b["period"] for b in bars] == ["1919-1949", "1973-1985-west"]
    assert [b["period"] for b in rent_by_period(ROWS, "medium", True, 38, PERIODS)] == [
        "1919-1949",
        "1973-1990-east",
    ]


def test_explanation_only_uses_the_result_numbers():
    r = check(cold_rent_eur=60 * 9.03)
    text = explain(r, size_m2=60, year_built=1930, location_class="medium", estimate=True)
    assert "€5.90–9.55/m²" in text and "€7.30" in text and "about €8.03/m²" in text
    assert "€60 a month over the limit" in text


def test_every_checklist_rule_names_a_real_item_and_period():
    for item_id, periods in NOT_APPLICABLE.items():
        assert item_id in LABELS
        assert periods <= set(PERIODS)
