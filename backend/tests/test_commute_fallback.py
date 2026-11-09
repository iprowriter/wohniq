"""Live commute falls back to an offline estimate instead of nothing (ADR-0008).

The BVG/VBB calls are stubbed; no network. Estimates must never be cached as if they
were real journeys, and a successful live lookup must behave exactly as before.
"""

import httpx
import pytest

import enrich.commute as commute
from data.models import CommuteCache
from enrich.commute_estimate import estimate_commute
from enrich.places import Place

LISTING = (52.499, 13.403)  # Kreuzberg
ALEX = Place("S+U Alexanderplatz", 52.5215, 13.4113, "vbb")


class _Session:
    def __init__(self, cached=None):
        self.cached, self.added, self.commits = cached, [], 0

    def get(self, model, key):
        return self.cached

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


def _raise(*a, **kw):
    raise httpx.ConnectError("transit API down")


@pytest.fixture
def places(monkeypatch):
    lookups = []

    def resolve(text):
        lookups.append(text)
        return ALEX if text == "Alexanderplatz" else None

    monkeypatch.setattr(commute, "resolve_place", resolve)
    return lookups


def test_api_down_falls_back_to_estimate_and_does_not_cache(monkeypatch, places):
    monkeypatch.setattr(commute, "resolve_location", _raise)
    session = _Session()

    result = commute.get_commute(session, *LISTING, "Alexanderplatz")

    assert result == estimate_commute(*LISTING, ALEX.lat, ALEX.lng)
    assert result.estimated is True
    assert session.added == [] and session.commits == 0
    assert places == ["Alexanderplatz"]


def test_journey_failure_uses_the_stop_the_api_resolved(monkeypatch, places):
    # The API found the stop (with coordinates) but the journey request failed: use
    # VBB's coordinates rather than our own lookup.
    stop = {"id": "900100003", "location": {"latitude": 52.52, "longitude": 13.41}}
    monkeypatch.setattr(commute, "resolve_location", lambda q: stop)
    monkeypatch.setattr(commute, "fetch_first_journey", _raise)

    result = commute.get_commute(_Session(), *LISTING, "Alexanderplatz")

    assert result == estimate_commute(*LISTING, 52.52, 13.41)
    assert places == []  # local lookup not needed


def test_no_journey_found_falls_back_to_estimate(monkeypatch, places):
    monkeypatch.setattr(commute, "resolve_location", lambda q: None)  # API knows no such stop
    result = commute.get_commute(_Session(), *LISTING, "Alexanderplatz")
    assert result is not None and result.estimated is True


def test_unknown_place_with_api_down_returns_none(monkeypatch, places):
    monkeypatch.setattr(commute, "resolve_location", _raise)
    assert commute.get_commute(_Session(), *LISTING, "Google office") is None


def test_live_success_is_unchanged_and_cached(monkeypatch, places):
    monkeypatch.setattr(commute, "resolve_location", lambda q: {"id": "900100003"})
    monkeypatch.setattr(commute, "fetch_first_journey", lambda *a: {"legs": []})
    live = commute.CommuteResult(minutes=23, changes=1, walk_minutes=6)
    monkeypatch.setattr(commute, "parse_journey", lambda j: live)
    session = _Session()

    result = commute.get_commute(session, *LISTING, "Alexanderplatz")

    assert result is live and result.estimated is False
    assert len(session.added) == 1 and session.commits == 1
    assert places == []


def test_cached_live_result_is_not_estimated(monkeypatch):
    monkeypatch.setattr(commute, "resolve_location", _raise)  # must not be reached
    row = CommuteCache(minutes=18, changes=0, walk_minutes=4)
    result = commute.get_commute(_Session(cached=row), *LISTING, "Alexanderplatz")
    assert (result.minutes, result.estimated) == (18, False)


def test_stop_coords_shapes():
    assert commute._stop_coords(None) is None
    assert commute._stop_coords({"id": "x"}) is None
    assert commute._stop_coords({"location": {"latitude": 1, "longitude": 2}}) == (1.0, 2.0)
    assert commute._stop_coords({"type": "location", "latitude": 3, "longitude": 4}) == (3.0, 4.0)
