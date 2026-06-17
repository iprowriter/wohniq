"""Unit tests for the hard-filter spec (pure, no DB)."""

from search.filters import build_hard_filters


def test_no_criteria_no_filters():
    assert build_hard_filters(None, None, None) == []


def test_budget_is_ceiling_on_warm_rent():
    assert build_hard_filters(1500, None, None) == [("warmmiete_eur", "<=", 1500)]


def test_rooms_and_size_are_minimums():
    filters = build_hard_filters(None, 2, 60)
    assert ("rooms", ">=", 2) in filters
    assert ("size_m2", ">=", 60) in filters


def test_all_three_together():
    filters = build_hard_filters(1800, 2.5, 70)
    assert filters == [
        ("warmmiete_eur", "<=", 1800),
        ("rooms", ">=", 2.5),
        ("size_m2", ">=", 70),
    ]
