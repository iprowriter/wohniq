"""Around this flat, Right now, listing context and the Berlin API (ADR-0016/0017).

Pure parts always run; the rest needs `make berlin-data` and runs in offline demo mode.
"""

from __future__ import annotations

import pytest

from berlin import files
from berlin.departures import api_stop_id, parse_departures, right_now
from berlin.profile import count_sentence, distance_sentence, walk_min
from berlin.repository import Stop

needs_build = pytest.mark.skipif(not files.is_built(), reason="run `make berlin-data` first")


# --- wording (pure) -------------------------------------------------------------------


def test_walking_minutes_match_the_project_walking_model():
    assert walk_min(188) == 4  # 188 m × 1.3 detour at 4.8 km/h = 3.1 min → 4
    assert walk_min(10) == 1


def test_distance_sentences_say_closer_or_farther():
    values = [100, 200, 300, 400, 500]
    assert distance_sentence(150, values) == ("Closer than 80% of Berlin's 542 planning areas", 80)
    text, position = distance_sentence(450, values)
    assert text == "Farther than 80% of Berlin's 542 planning areas" and position == 20


def test_count_sentences_say_more_or_fewer():
    values = [1, 2, 3, 4, 5]
    assert count_sentence(5.5, values)[0] == "More than in 100% of Berlin's 542 planning areas"
    assert count_sentence(1.5, values)[0] == "Fewer than in 80% of Berlin's 542 planning areas"


# --- Right now (pure, with a saved sample response) -----------------------------------

SAMPLE = {  # trimmed from a real v6.bvg.transport.rest response, 2026-11-24
    "departures": [
        {
            "when": "2026-11-24T13:05:00+01:00",
            "plannedWhen": "2026-11-24T13:04:00+01:00",
            "delay": 60,
            "platform": "1",
            "direction": "S Lichtenrade (Berlin)",
            "line": {"name": "S2", "product": "suburban"},
            "stop": {"name": "S Nordbahnhof (Berlin)"},
            "cancelled": None,
        },
        {
            "when": None,
            "plannedWhen": "2026-11-24T13:03:00+01:00",
            "delay": None,
            "platform": "Pos. 5",
            "direction": "U Turmstr.",
            "line": {"name": "M8", "product": "tram"},
            "stop": {"name": "S Nordbahnhof (Berlin)"},
            "cancelled": True,
        },
    ]
}


def test_parse_departures():
    s2, m8 = parse_departures(SAMPLE)
    assert (s2.line, s2.mode, s2.delay_minutes, s2.platform, s2.stop) == (
        "S2",
        "sbahn",
        1,
        "1",
        "S Nordbahnhof",
    )
    assert m8.cancelled and m8.when == "2026-11-24T13:03:00+01:00" and m8.mode == "tram"


def test_api_stop_id():
    assert api_stop_id("de:11000:900007104") == "900007104"


class FakeData:
    def __init__(self):
        self.stops = [
            Stop("de:11000:1", "U A", ("ubahn",), 52.5, 13.4, 120.0),
            Stop("de:11000:2", "Tram B", ("tram",), 52.5, 13.4, 200.0),
            Stop("de:11000:3", "Bus C", ("bus",), 52.5, 13.4, 300.0),
        ]

    def nearest_stops(self, lat, lng, limit=6, modes=None):
        hits = [s for s in self.stops if not modes or set(s.modes) & modes]
        return hits[:limit]


def test_right_now_merges_live_departures_by_time():
    def fetch(stop_id):
        return parse_departures(SAMPLE) if stop_id.endswith(":1") else []

    out = right_now(FakeData(), 52.5, 13.4, fetch=fetch)
    assert out.status == "live" and "U A and Tram B" in out.note
    assert [d.line for d in out.departures] == ["M8", "S2"]  # sorted by time
    assert [s.walk_minutes for s in out.stops] == [2, 4, 5]


def test_right_now_falls_back_to_the_stop_list():
    def fetch(stop_id):
        raise TimeoutError

    out = right_now(FakeData(), 52.5, 13.4, fetch=fetch)
    assert out.status == "offline" and out.departures == []
    assert out.note.startswith("Nearest stop: U A · 2 min walk.")
    assert len(out.stops) == 3
    assert right_now(FakeData(), 52.5, 13.4, live=False).status == "offline"


# --- offline data: profile and listing context ----------------------------------------


@pytest.fixture(scope="module")
def local():
    from berlin.local import LocalBerlinData

    return LocalBerlinData()


@needs_build
def test_profile_has_the_eight_design_measures(local):
    from berlin.profile import build_profile

    p = build_profile(local, 52.52970, 13.40150)
    assert [m.key for m in p.measures] == [
        "rail",
        "schools",
        "kitas",
        "green",
        "air",
        "accidents",
        "crime",
        "location_class",
    ]
    by_key = {m.key: m for m in p.measures}
    assert by_key["rail"].headline == "U Rosenthaler Platz · 1 min walk"
    assert by_key["crime"].comparison == "Higher than in 96% of Berlin's 143 district regions"
    assert "6,622" in by_key["crime"].detail  # same figure as Berlin Neighbourhoods
    for m in p.measures:
        assert 0 <= m.position <= 100 and m.source and m.comparison
        for word in ("better", "worse", "safe", "dangerous", "good area", "bad area"):
            assert word not in m.comparison.lower()


@needs_build
def test_every_listing_tells_one_story(local):
    """Street, planning area and the profile all come from the matched address."""
    from berlin.listings import listing_location
    from berlin.profile import build_profile
    from data.synthetic import generate_listings

    for x in generate_listings(100, seed=42):
        loc = listing_location(local, x)
        assert loc.district == x.district
        area = local.area_at(loc.lat, loc.lng)
        assert area.plr_id == loc.plr_id or area.plr_name == loc.planning_area
        profile = build_profile(local, loc.lat, loc.lng, loc.location_class)
        assert profile.planning_area == loc.planning_area
        assert profile.district_region == loc.district_region


@needs_build
def test_listing_rents_after_the_overrides(local):
    from collections import Counter

    from berlin.listings import listing_rent
    from data.synthetic import generate_listings

    verdicts = Counter()
    for x in generate_listings(100, seed=42):
        v = listing_rent(local, x).result.verdict
        verdicts[v] += 1
        if x.scam_type == "price_bait":
            assert v == "below_index"
        elif not x.is_scam:
            assert v != "below_index"  # no honest listing looks like price bait
    assert verdicts["within_limit"] >= 25 and verdicts["new_build"] == 8


# --- API (offline demo mode) ----------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from core.config import settings

    monkeypatch.setattr(settings, "wohniq_demo", True)
    monkeypatch.setattr(settings, "wohniq_live_departures", False)  # no network in tests
    with TestClient(app) as c:
        yield c


@needs_build
def test_rent_index_endpoint(client):
    body = client.get("/api/v1/rent/index").json()
    assert len(body["rows"]) == 189 and len(body["checklist"]) == 83
    assert all(item["label"] for item in body["checklist"])
    assert "not legal advice" in body["disclaimer"] and "1 October 2014" in body["exemptions"]


@needs_build
def test_address_endpoints(client):
    hits = client.get("/api/v1/rent/addresses", params={"q": "Choriner Str. 41"}).json()
    assert hits[0]["label"] == "Choriner Straße 41, 10435 Berlin"
    detail = client.get(f"/api/v1/rent/addresses/{hits[0]['id']}", params={"size_m2": 61}).json()
    assert detail["planning_area"] == "Teutoburger Platz"
    assert detail["mean_by_period"][0] == {
        "period": "pre1918",
        "label": "before 1918",
        "mean": 9.46,
        "row": 135,
    }
    assert client.get("/api/v1/rent/addresses/999999999").status_code == 404
    assert client.get("/api/v1/rent/addresses", params={"q": "x"}).status_code == 422


@needs_build
def test_place_and_right_now_endpoints(client):
    p = client.get("/api/v1/place", params={"lat": 52.5297, "lng": 13.4015}).json()
    assert len(p["measures"]) == 8 and p["district"] == "Mitte"
    rn = client.get("/api/v1/right-now", params={"lat": 52.5297, "lng": 13.4015}).json()
    assert rn["status"] == "offline" and rn["stops"][0]["name"] == "U Rosenthaler Platz"
    assert client.get("/api/v1/place", params={"lat": 48.13, "lng": 11.57}).status_code == 422


@needs_build
def test_listings_carry_location_and_rent(client):
    listings = client.get("/api/v1/listings/random", params={"n": 6}).json()
    for x in listings:
        assert x["year_built"] and x["location"]["street"] and x["rent"]["verdict"]
        assert x["rent"]["estimate"] is True
    one = listings[0]
    detail = client.get(f"/api/v1/listings/{one['id']}").json()
    assert detail["location"] == one["location"] and detail["rent"] == one["rent"]
    around = client.get(f"/api/v1/listings/{one['id']}/around").json()
    assert around["planning_area"] == one["location"]["planning_area"]


@needs_build
def test_listing_commute_endpoint(client):
    lid = client.get("/api/v1/listings/random", params={"n": 1}).json()[0]["id"]
    ok = client.get(f"/api/v1/listings/{lid}/commute", params={"to": "Alexanderplatz"}).json()
    assert ok["commute"]["minutes"] > 0 and ok["commute"]["estimated"] is True
    unknown = client.get(f"/api/v1/listings/{lid}/commute", params={"to": "Nowhereville"}).json()
    assert unknown["commute"] is None and "Couldn't find" in unknown["note"]
    assert client.get(f"/api/v1/listings/{lid}/commute", params={"to": "x"}).status_code == 422
