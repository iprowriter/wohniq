"""Unit tests for the transport.rest journey parser (pure, no network)."""

from enrich.commute_parse import parse_journey

# A walk → U-Bahn journey: 4 min walk, then one transit leg. 0 changes.
DIRECT = {
    "legs": [
        {"walking": True, "departure": "2026-07-01T08:00:00+02:00", "arrival": "2026-07-01T08:04:00+02:00"},
        {"line": {"name": "U2"}, "departure": "2026-07-01T08:06:00+02:00", "arrival": "2026-07-01T08:22:00+02:00"},
    ]
}

# Two transit legs with a change in the middle. 1 change.
ONE_CHANGE = {
    "legs": [
        {"line": {"name": "U8"}, "departure": "2026-07-01T08:00:00+02:00", "arrival": "2026-07-01T08:10:00+02:00"},
        {"walking": True, "departure": "2026-07-01T08:10:00+02:00", "arrival": "2026-07-01T08:13:00+02:00"},
        {"line": {"name": "S7"}, "departure": "2026-07-01T08:15:00+02:00", "arrival": "2026-07-01T08:30:00+02:00"},
    ]
}


def test_direct_journey():
    result = parse_journey(DIRECT)
    assert result is not None
    assert result.minutes == 22  # 08:00 → 08:22
    assert result.changes == 0  # one transit leg
    assert result.walk_minutes == 4


def test_journey_with_one_change():
    result = parse_journey(ONE_CHANGE)
    assert result.minutes == 30  # 08:00 → 08:30
    assert result.changes == 1  # two transit legs
    assert result.walk_minutes == 3


def test_empty_journey_returns_none():
    assert parse_journey({"legs": []}) is None
    assert parse_journey({}) is None


def test_no_walking_legs_means_none_walk():
    only_transit = {
        "legs": [
            {"line": {"name": "U2"}, "departure": "2026-07-01T08:00:00+02:00", "arrival": "2026-07-01T08:18:00+02:00"},
        ]
    }
    result = parse_journey(only_transit)
    assert result.minutes == 18 and result.changes == 0 and result.walk_minutes is None
