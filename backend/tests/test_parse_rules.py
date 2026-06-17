"""Unit tests for the deterministic keyword extractor (pure, no pydantic/network)."""

from search.parse_rules import extract_criteria


def test_budget_formats():
    assert extract_criteria("budget €1,500")["max_warm_rent"] == 1500
    assert extract_criteria("1.500 EUR per month")["max_warm_rent"] == 1500
    assert extract_criteria("budget of 1200")["max_warm_rent"] == 1200
    assert extract_criteria("no price mentioned")["max_warm_rent"] is None


def test_rooms_and_size():
    assert extract_criteria("a 2-room flat")["min_rooms"] == 2.0
    assert extract_criteria("1.5 zimmer")["min_rooms"] == 1.5
    assert extract_criteria("around 60 m²")["min_size_m2"] == 60


def test_priority_flags():
    assert extract_criteria("a quiet residential street")["quiet_priority"] is True
    assert extract_criteria("good public transport")["transport_priority"] is True
    assert extract_criteria("a flat")["quiet_priority"] is False


def test_amenities_map_to_canonical():
    out = extract_criteria("cafes nearby, a park, and some bars")
    assert set(out["desired_amenities"]) == {"cafes", "parks", "nightlife"}


def test_furnished_detection():
    assert extract_criteria("furnished flat")["furnished"] is True
    assert extract_criteria("unfurnished please")["furnished"] is False
    assert extract_criteria("a flat")["furnished"] is None


def test_notes_preserves_raw_text():
    q = "somewhere I can bike to work"
    assert extract_criteria(q)["notes"] == q
