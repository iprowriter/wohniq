"""Offline commute estimate (pure): haversine, walk vs. transit, rounding, monotonicity."""

import pytest

from enrich import commute_estimate as ce


def test_haversine_one_degree_of_latitude():
    # One degree of latitude on the mean-radius sphere is 2πR/360 ≈ 111.195 km.
    assert ce.haversine_km(52.0, 13.0, 53.0, 13.0) == pytest.approx(111.195, abs=0.01)


def test_haversine_is_symmetric_and_zero_for_same_point():
    a, b = (52.5215, 13.4113), (52.5069, 13.3327)
    assert ce.haversine_km(*a, *b) == pytest.approx(ce.haversine_km(*b, *a))
    assert ce.haversine_km(*a, *a) == 0.0


def test_published_speeds_are_ordered_by_mode():
    assert ce.BUS_TRAM_KMH < ce.UBAHN_KMH < ce.SBAHN_KMH


def test_short_trips_walk_long_trips_ride():
    assert ce.walk_minutes(0.5) < ce.transit_minutes(0.5)
    assert ce.transit_minutes(5.0) < ce.walk_minutes(5.0)


def test_estimate_never_decreases_with_distance():
    # A farther listing must never look closer (otherwise ranking would reward it).
    prev = 0.0
    for i in range(3001):  # 0–30 km in 10 m steps, unrounded
        d = i / 100
        cur = min(ce.walk_minutes(d), ce.transit_minutes(d))
        assert cur >= prev - 1e-9, d
        prev = cur


def test_transit_formula_matches_documented_model():
    # 10 km: 2 km bus/tram + 4 km U-Bahn + 4 km S-Bahn, 1.2 detour, one change.
    expected = (
        ce.ACCESS_EGRESS_MIN
        + ce.INITIAL_WAIT_MIN
        + 2 * 1.2 / ce.BUS_TRAM_KMH * 60
        + 4 * 1.2 / ce.UBAHN_KMH * 60
        + 4 * 1.2 / ce.SBAHN_KMH * 60
        + ce.TRANSFER_MIN
    )
    assert ce.transit_minutes(10.0) == pytest.approx(expected)


@pytest.mark.parametrize(("raw", "shown"), [(0.4, 5), (3.0, 5), (7.4, 5), (7.6, 10), (33.0, 35)])
def test_rounded_to_5_minutes_with_minimum_5(raw, shown):
    assert ce.round_to_5(raw) == shown


def test_estimate_result_is_flagged_and_reports_minutes_only():
    result = ce.estimate_commute(52.5215, 13.4113, 52.5069, 13.3327)  # ~5.6 km
    assert result.estimated is True
    assert result.changes is None and result.walk_minutes is None
    assert result.minutes % 5 == 0
    assert 20 <= result.minutes <= 40
