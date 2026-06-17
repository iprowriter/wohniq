"""Unit tests for the pure eval scorer (no pydantic/network)."""

from evals.scoring import match_field, score_case, summarize


def test_match_scalar_and_none():
    assert match_field(1500, 1500) is True
    assert match_field(1500, 1400) is False
    assert match_field(None, None) is True
    assert match_field(None, 900) is False  # hallucinated value fails
    assert match_field(2, 2.0) is True  # int/float equality


def test_match_list_is_set_insensitive():
    assert match_field(["cafes", "parks"], ["PARKS", "cafes"]) is True
    assert match_field(["cafes"], ["cafes", "parks"]) is False
    assert match_field(["cafes"], None) is False


def test_match_string_is_containment():
    assert match_field("Alexanderplatz", "near Alexanderplatz") is True
    assert match_field("Mitte", "Kreuzberg") is False


def test_score_case_only_checks_expected_fields():
    expected = {"max_warm_rent": 1500, "quiet_priority": True}
    actual = {"max_warm_rent": 1500, "quiet_priority": False, "min_rooms": 2}
    result = score_case(expected, actual)
    assert result == {"max_warm_rent": True, "quiet_priority": False}


def test_summarize_metrics():
    results = [
        {"a": True, "b": True},
        {"a": True, "b": False},
    ]
    s = summarize(results)
    assert s["cases"] == 2
    assert s["cases_fully_correct"] == 1
    assert s["case_accuracy"] == 0.5
    assert s["fields_checked"] == 4
    assert s["fields_correct"] == 3
    assert s["field_accuracy"] == 0.75
