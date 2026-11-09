"""Offline demo mode: trigger rules, fixture integrity, and the full API with no network.

The end-to-end tests block every outbound socket/DNS call, so any hidden dependency on
Supabase, Gemini, Overpass, or VBB fails loudly instead of silently hanging a demo.
"""

import socket
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

import core.llm as llm
from app.main import app
from core.config import Settings, settings
from data.demo_repository import DemoRepository, get_demo_repository
from enrich.neighborhood import _location_key

EXAMPLE = (
    "I work near Alexanderplatz, budget €1,500, quiet neighborhood, good transport, " "cafes nearby"
)


# --- Trigger rules -----------------------------------------------------------------
# Precedence: WOHNIQ_DEMO=1 wins; else an empty DATABASE_URL means demo; else live.

LIVE_URL = "postgresql://u:p@db.example.invalid:5432/wohniq"


@pytest.fixture
def clean_env(monkeypatch):
    """Keep the developer's shell env out of Settings() in these tests."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("WOHNIQ_DEMO", raising=False)
    return monkeypatch


def _settings_from_env_file(tmp_path, text: str) -> Settings:
    env_file = tmp_path / ".env"
    env_file.write_text(text, encoding="utf-8")
    return Settings(_env_file=env_file)


@pytest.mark.parametrize(
    ("database_url", "wohniq_demo", "expected"),
    [
        ("", "", True),  # nothing configured -> demo
        ("   ", "", True),  # whitespace-only URL counts as empty
        ("", "0", True),  # flag off can't make it live: there's no DB to use
        ("", "1", True),
        (LIVE_URL, "", False),  # empty flag = not forced -> live
        (LIVE_URL, "0", False),
        (LIVE_URL, "1", True),  # flag wins over the URL
    ],
)
def test_precedence_table(clean_env, database_url, wohniq_demo, expected):
    s = Settings(_env_file=None, database_url=database_url, wohniq_demo=wohniq_demo)
    assert s.demo_mode is expected


def test_demo_flag_wins_over_database_url_in_env_file(clean_env, tmp_path):
    s = _settings_from_env_file(tmp_path, f"DATABASE_URL={LIVE_URL}\nWOHNIQ_DEMO=1\n")
    assert s.database_url == LIVE_URL  # the URL is read...
    assert s.demo_mode is True  # ...but demo mode still wins
    assert "overrides DATABASE_URL" in s.demo_mode_reason


def test_demo_flag_wins_over_database_url_in_environment(clean_env, tmp_path):
    clean_env.setenv("DATABASE_URL", LIVE_URL)
    clean_env.setenv("WOHNIQ_DEMO", "1")
    s = Settings(_env_file=tmp_path / "does-not-exist.env")
    assert s.demo_mode is True
    assert "overrides DATABASE_URL" in s.demo_mode_reason


def test_empty_demo_flag_in_env_file_is_not_forced(clean_env, tmp_path):
    # `WOHNIQ_DEMO=` (as in a copied .env.example) must not switch demo mode on.
    s = _settings_from_env_file(tmp_path, f"DATABASE_URL={LIVE_URL}\nWOHNIQ_DEMO=\n")
    assert s.wohniq_demo is False
    assert s.demo_mode is False
    assert s.demo_mode_reason is None


def test_env_example_template_defaults_to_not_forced(clean_env):
    template = Path(__file__).resolve().parents[2] / ".env.example"
    s = Settings(_env_file=template)
    assert s.wohniq_demo is False
    assert s.demo_mode_reason == "DATABASE_URL is empty"  # until the URL is filled in


@pytest.mark.parametrize("bad", ["ture", "2", "demo", "enabled"])
def test_unrecognised_demo_flag_is_rejected(clean_env, bad):
    # A typo must fail at startup, not silently fall through to the live database.
    with pytest.raises(ValidationError, match="WOHNIQ_DEMO"):
        Settings(_env_file=None, database_url=LIVE_URL, wohniq_demo=bad)


def test_missing_env_file_means_demo(clean_env, tmp_path):
    s = Settings(_env_file=tmp_path / "does-not-exist.env")
    assert s.demo_mode is True
    assert s.demo_mode_reason == "DATABASE_URL is empty"


def test_db_url_from_real_env_stays_live_without_env_file(clean_env, tmp_path):
    # e.g. Railway: no .env file, DATABASE_URL injected as an environment variable.
    clean_env.setenv("DATABASE_URL", LIVE_URL)
    assert Settings(_env_file=tmp_path / "does-not-exist.env").demo_mode is False


def test_demo_flag_with_database_url_never_touches_the_database(monkeypatch):
    """Both set: the API serves fixtures and never builds a DB session or opens a socket."""
    import app.repository as repository

    def no_db(*a, **kw):
        raise AssertionError("database used although WOHNIQ_DEMO=1")

    def no_network(*a, **kw):
        raise AssertionError(f"network access attempted: {a}")

    monkeypatch.setattr(settings, "database_url", LIVE_URL)
    monkeypatch.setattr(settings, "wohniq_demo", True)
    monkeypatch.setattr(repository, "get_sessionmaker", no_db)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    app.dependency_overrides.clear()

    gen = repository.get_repository()
    assert isinstance(next(gen), DemoRepository)
    gen.close()

    client = TestClient(app)
    assert client.get("/api/v1/health").json()["mode"] == "demo"
    listings = client.get("/api/v1/listings/random?n=3")
    assert listings.status_code == 200 and len(listings.json()) == 3
    detail = client.get(f"/api/v1/listings/{listings.json()[0]['id']}")
    assert detail.status_code == 200
    search = client.post("/api/v1/search", json={"query": "quiet flat under €1500"})
    assert search.status_code == 200 and search.json()["results"]


def test_database_url_without_flag_uses_the_database(monkeypatch):
    """Control case for the test above: same URL, flag off -> the SQL repository."""
    import app.repository as repository

    opened = []

    class _Session:
        def __enter__(self):
            opened.append(True)
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(settings, "database_url", LIVE_URL)
    monkeypatch.setattr(settings, "wohniq_demo", False)
    monkeypatch.setattr(repository, "get_sessionmaker", lambda: _Session)

    gen = repository.get_repository()
    assert isinstance(next(gen), repository.SqlRepository)
    gen.close()
    assert opened == [True]


# --- LLM short-circuit -------------------------------------------------------------


class _Out(BaseModel):
    value: str


def test_llm_uses_fallback_without_calling_gemini(monkeypatch):
    monkeypatch.setattr(settings, "wohniq_demo", True)

    def boom(*a, **kw):
        raise AssertionError("Gemini must not be called in demo mode")

    monkeypatch.setattr(llm, "_call_gemini", boom)
    result = llm.generate_structured(
        prompt_id="t", system="s", user="u", schema=_Out, fallback=lambda: _Out(value="fb")
    )
    assert result.data.value == "fb"
    assert result.used_fallback is True

    with pytest.raises(llm.LLMError):
        llm.generate_structured(prompt_id="t", system="s", user="u", schema=_Out)


# --- Fixtures ----------------------------------------------------------------------


def test_fixtures_are_complete_and_consistent():
    repo = DemoRepository()  # raises if generator and fixtures drifted
    listings = list(repo._listings.values())
    assert len(listings) == 100
    # Every featured listing can render a complete detail page.
    assert len(repo._featured) >= 6
    for x in repo._featured:
        nb = repo.neighborhood(x.lat, x.lng)
        assert nb is not None and nb.pois and nb.counts
        assert len(repo.photos_by_set([x.photo_set_id])[x.photo_set_id]) == 5
        assert str(x.id) in repo.risk_by_listing([x.id])


def test_photo_url_prefers_local_copy(monkeypatch, tmp_path):
    import data.demo_repository as demo

    repo = get_demo_repository()
    listing = repo._featured[0]
    hotlinked = repo.photos_by_set([listing.photo_set_id])[listing.photo_set_id][0].source_url
    assert hotlinked.startswith("https://images.pexels.com/")

    monkeypatch.setattr(demo, "PHOTOS_DIR", tmp_path)
    (tmp_path / demo.local_photo_name(hotlinked)).write_bytes(b"jpeg")
    local = repo.photos_by_set([listing.photo_set_id])[listing.photo_set_id][0].source_url
    assert local == f"/demo-photos/{demo.local_photo_name(hotlinked)}"


def test_demo_retrieval_applies_hard_filters():
    from search.criteria import SearchCriteria

    repo = get_demo_repository()
    results = repo.retrieve(
        SearchCriteria(max_warm_rent=1200, min_rooms=2), "quiet flat", limit=100
    )
    assert results
    assert all(r.listing.warmmiete_eur <= 1200 and r.listing.rooms >= 2 for r in results)


def test_demo_retrieval_prefers_requested_kiez():
    from search.criteria import SearchCriteria

    repo = get_demo_repository()
    kiez = repo._featured[0].kiez
    top = repo.retrieve(SearchCriteria(), f"flat in {kiez}", limit=3)
    assert all(r.listing.kiez == kiez for r in top)


# --- End to end, network blocked ---------------------------------------------------


@pytest.fixture
def offline_client(monkeypatch):
    def no_network(*a, **kw):
        raise AssertionError(f"network access attempted in demo mode: {a}")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(settings, "wohniq_demo", True)
    app.dependency_overrides.clear()
    return TestClient(app)


def test_health_reports_demo(offline_client):
    assert offline_client.get("/api/v1/health").json()["mode"] == "demo"


def test_home_listings_open_to_complete_detail_pages(offline_client):
    resp = offline_client.get("/api/v1/listings/random?n=6")
    assert resp.status_code == 200
    featured = resp.json()
    assert len(featured) == 6
    assert len({x["id"] for x in featured}) == 6

    for card in featured:
        assert card["photos"], card["title"]
        assert "is_scam" not in card and "scam_type" not in card

        detail = offline_client.get(f"/api/v1/listings/{card['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["listing"]["id"] == card["id"]
        assert len(body["listing"]["photos"]) == 5
        assert body["risk"]["band"] in {"low", "caution", "high"}
        assert 0 <= body["risk"]["score"] <= 100
        assert body["neighborhood"]["pois"]
        assert body["neighborhood"]["radius_m"] == 500  # amenity search radius, for the map
        assert any(n > 0 for n in body["neighborhood"]["counts"].values())
        assert "is_scam" not in body["listing"]


@pytest.fixture
def places(monkeypatch):
    """Pin the offline place index so tests don't depend on `make demo-stops` having run."""
    import enrich.commute as commute
    from enrich.places import PlaceIndex

    index = PlaceIndex(
        [{"name": "S+U Alexanderplatz", "lat": "52.5215", "lng": "13.4113", "location_type": ""}]
    )
    monkeypatch.setattr(commute, "resolve_place", index.resolve)
    return index


def test_example_search_works_offline(offline_client, places):
    resp = offline_client.post("/api/v1/search", json={"query": EXAMPLE, "limit": 6})
    assert resp.status_code == 200
    data = resp.json()
    assert data["criteria"]["max_warm_rent"] == 1500
    assert data["criteria"]["quiet_priority"] is True
    assert data["results"]
    for item in data["results"]:
        assert item["listing"]["warmmiete_eur"] <= 1500
        assert item["listing"]["photos"]
        assert item["explanation"]["summary"]
        assert item["risk"] is not None
        # "I work near Alexanderplatz" → offline estimate: minutes only, flagged.
        commute = item["commute"]
        assert commute["estimated"] is True and commute["source"] == "distance"
        assert commute["changes"] is None
        assert commute["minutes"] % 5 == 0 and 5 <= commute["minutes"] <= 90
        factor = next(f for f in item["factors"] if f["name"] == "commute")
        assert factor["weight"] == 1.0  # estimates count half (ADR-0008)
        assert factor["detail"].endswith("min to work (estimated)")
    assert "estimates" in data["commute_note"]
    scores = [item["score"] for item in data["results"]]
    assert scores == sorted(scores, reverse=True)


def test_example_search_uses_route_based_estimate_when_network_present(
    offline_client, places, monkeypatch
):
    """Wiring: with a VBB network, commutes are routed (real changes, weight 1.5).

    Routing itself is tested in test_transit_network.py; here a stub network returns a
    fixed route so the test doesn't depend on where the listings are.
    """
    import enrich.commute as commute
    from enrich.transit_network import Route

    class StubNetwork:
        def route(self, lat, lng, dlat, dlng):
            legs = ["walk 5 min to U Stub", "U5 U Stub → S+U Alexanderplatz (12 min incl. wait)"]
            return Route(minutes=23.4, changes=1, walk_minutes=7.2, legs=legs)

    monkeypatch.setattr(commute, "get_network", lambda: StubNetwork())

    data = offline_client.post("/api/v1/search", json={"query": EXAMPLE, "limit": 6}).json()
    assert "VBB timetable" in data["commute_note"]
    assert data["results"]
    for item in data["results"]:
        c = item["commute"]
        assert (c["minutes"], c["changes"], c["walk_minutes"]) == (23, 1, 7)
        assert c["source"] == "network" and c["estimated"] is True
        factor = next(f for f in item["factors"] if f["name"] == "commute")
        assert factor["weight"] == 1.5
        assert factor["detail"] == "≈23 min to work, 1 change (estimated)"


def test_commute_to_a_kiez_works_without_the_stops_file(offline_client, monkeypatch):
    import enrich.commute as commute
    from enrich.places import PlaceIndex

    monkeypatch.setattr(commute, "resolve_place", PlaceIndex([]).resolve)  # no stops file
    resp = offline_client.post("/api/v1/search", json={"query": "I work near Kreuzberg"})
    results = resp.json()["results"]
    assert results and all(r["commute"]["estimated"] for r in results)


def test_unknown_work_location_explains_missing_commute(offline_client, places):
    resp = offline_client.post("/api/v1/search", json={"query": "I work near Narnia Castle"})
    data = resp.json()
    assert data["criteria"]["work_location"] == "Narnia Castle"
    assert all(r["commute"] is None for r in data["results"])
    assert data["commute_note"] == "Couldn't find \"Narnia Castle\", so commute times aren't shown."


def test_no_work_location_means_no_commute_note(offline_client, places):
    data = offline_client.post("/api/v1/search", json={"query": "quiet flat"}).json()
    assert data["commute_note"] is None
    assert all(r["commute"] is None for r in data["results"])


def test_compare_works_offline(offline_client, places):
    ids = [x["id"] for x in offline_client.get("/api/v1/listings/random?n=2").json()]
    resp = offline_client.post(
        "/api/v1/compare",
        json={"listing_ids": ids, "query": "I work near Alexanderplatz, budget €2000, cafes"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["listing"]["id"] for i in items] == ids
    assert all(i["fit_score"] is not None and i["risk"] for i in items)
    assert all(i["commute"]["estimated"] for i in items)


def test_unknown_listing_is_404_offline(offline_client):
    assert offline_client.get(f"/api/v1/listings/{uuid.uuid4()}").status_code == 404
    assert offline_client.get("/api/v1/listings/not-a-uuid").status_code == 400


def test_featured_listings_have_neighborhood_cache_keys():
    repo = get_demo_repository()
    keys = {_location_key(x.lat, x.lng) for x in repo._featured}
    assert keys <= set(repo._neighborhoods)
