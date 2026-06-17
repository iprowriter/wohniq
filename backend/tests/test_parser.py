"""Tests for parse_query: the LLM path (fake transport) and the fallback path."""

from core.llm import RawResponse
from search.parser import keyword_fallback, parse_query


def _transport_returning(*texts):
    calls = iter(texts)

    def transport(system, user, schema, temperature):
        return RawResponse(text=next(calls), tokens_in=8, tokens_out=4)

    return transport


def test_llm_path_returns_parsed_criteria():
    raw = (
        '{"max_warm_rent": 1500, "min_rooms": 2, "min_size_m2": null, '
        '"work_location": "Alexanderplatz", "transport_priority": true, '
        '"quiet_priority": true, "desired_amenities": ["cafes"], '
        '"furnished": null, "notes": null}'
    )
    crit = parse_query("…", transport=_transport_returning(raw))
    assert crit.max_warm_rent == 1500
    assert crit.work_location == "Alexanderplatz"
    assert crit.quiet_priority is True
    assert crit.desired_amenities == ["cafes"]


def test_non_canonical_amenities_are_filtered():
    raw = '{"desired_amenities": ["cafes", "rooftop pool", "PARKS"]}'
    crit = parse_query("…", transport=_transport_returning(raw))
    assert crit.desired_amenities == ["cafes", "parks"]


def test_falls_back_to_keywords_on_bad_output():
    # Transport always returns garbage → both attempts fail → keyword fallback.
    crit = parse_query(
        "quiet 2-room near Alexanderplatz, budget €1,500, cafes",
        transport=_transport_returning("nope", "still nope"),
    )
    assert crit.max_warm_rent == 1500
    assert crit.min_rooms == 2.0
    assert crit.quiet_priority is True
    assert "cafes" in crit.desired_amenities


def test_keyword_fallback_direct():
    crit = keyword_fallback("furnished 3 rooms, 70 m², good transport")
    assert crit.furnished is True
    assert crit.min_rooms == 3.0
    assert crit.min_size_m2 == 70
    assert crit.transport_priority is True
