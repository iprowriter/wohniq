"""Unit tests for the pure explanation selection logic (no pydantic/network)."""

from search.explain_rules import select_reasons_and_caveats, summary_lead


def test_relevance_excluded_strong_become_reasons():
    factors = [
        ("relevance", 0.9, 1.0, "semantic match 90%"),
        ("budget", 0.8, 1.5, "€150 under budget"),
        ("commute", 0.7, 2.0, "18 min to work"),
    ]
    reasons, caveats = select_reasons_and_caveats(factors)
    assert "semantic match 90%" not in reasons  # relevance is internal
    assert "18 min to work" in reasons and "€150 under budget" in reasons
    assert caveats == []


def test_weak_factors_become_caveats():
    factors = [
        ("budget", 0.9, 1.5, "€300 under budget"),
        ("quiet", 0.1, 1.0, "high nightlife"),
        ("amenities", 0.0, 1.0, "0 of 2 amenities nearby"),
    ]
    reasons, caveats = select_reasons_and_caveats(factors)
    assert "€300 under budget" in reasons
    assert "high nightlife" in caveats
    assert "0 of 2 amenities nearby" in caveats


def test_reasons_ordered_by_score_times_weight_and_capped():
    factors = [
        ("budget", 0.7, 1.5, "budget"),     # 1.05
        ("commute", 0.9, 2.0, "commute"),   # 1.80 -> first
        ("quiet", 0.8, 1.0, "quiet"),       # 0.80
        ("amenities", 0.65, 1.0, "amen"),   # 0.65
    ]
    reasons, _ = select_reasons_and_caveats(factors)
    assert reasons[0] == "commute"
    assert len(reasons) == 3  # capped


def test_always_at_least_one_reason():
    factors = [("amenities", 0.3, 1.0, "1 of 3 amenities nearby")]
    reasons, caveats = select_reasons_and_caveats(factors)
    assert reasons == ["1 of 3 amenities nearby"]  # best, even though below threshold
    assert caveats == ["1 of 3 amenities nearby"]


def test_summary_lead_thresholds():
    assert summary_lead(0.8) == "A strong match"
    assert summary_lead(0.6) == "A solid fit"
    assert summary_lead(0.3) == "A partial match"
