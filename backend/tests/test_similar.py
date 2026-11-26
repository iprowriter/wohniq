"""Similar apartments (T9.7): deterministic, explainable, and the exclusions hold."""

import socket

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.config import settings
from data.demo_repository import get_demo_repository
from search.similar import Flat, rank_similar, reasons

T = Flat(
    id="t",
    lat=52.53,
    lng=13.40,
    rooms=2,
    size_m2=50,
    warm_eur=1000,
    planning_area="A",
    district="Mitte",
    period="1919-1949",
    rent_verdict="within_limit",
    photo_set_id="p0",
)


def flat(id: str, **kw) -> Flat:
    base = dict(
        lat=52.53,
        lng=13.40,
        rooms=2,
        size_m2=50,
        warm_eur=1000,
        planning_area="A",
        district="Mitte",
        period="1919-1949",
        photo_set_id=f"p_{id}",
    )
    return Flat(id=id, **(base | kw))


def test_identical_flat_next_door_ranks_first_and_far_or_different_ones_lower():
    near_same = flat("a")
    far = flat("b", lat=52.45, lng=13.55, planning_area="Z", district="Neukölln")
    bigger = flat("c", rooms=4, size_m2=110, warm_eur=2200)
    out, fair_first = rank_similar(T, [bigger, far, near_same])
    assert [s.id for s in out] == ["a", "b", "c"]
    assert out[0].score == pytest.approx(1.0)
    assert not fair_first


def test_excludes_the_flat_itself_and_copies_of_its_photos_but_keeps_any_risk_level():
    me = flat("t")
    copy = flat("copy", photo_set_id="p0")
    other = flat("x")
    out, _ = rank_similar(T, [me, copy, other])
    assert [s.id for s in out] == ["x"]


def test_same_result_every_time_ties_broken_by_distance_then_id():
    cands = [flat(f"id{i}") for i in (3, 1, 2)]
    first, _ = rank_similar(T, cands)
    for _ in range(3):
        assert rank_similar(T, list(reversed(cands)))[0] == first
    assert [s.id for s in first] == ["id1", "id2", "id3"]


def test_flats_within_the_limit_come_first_when_this_one_is_above_it():
    target = flat("t", rent_verdict="above_limit", photo_set_id="p0")
    pricey_twin = flat("twin", rent_verdict="above_limit")
    fair_far = flat("fair", rent_verdict="within_limit", lat=52.50, lng=13.45)
    out, fair_first = rank_similar(target, [pricey_twin, fair_far])
    assert fair_first
    assert [s.id for s in out] == ["fair", "twin"]
    # Not when the flat itself is fair.
    out2, ff2 = rank_similar(flat("t2", rent_verdict="within_limit"), [pricey_twin, fair_far])
    assert not ff2 and out2[0].id == "twin"


def test_reasons_restate_the_numbers():
    other = flat("o", rooms=2.5, size_m2=48, warm_eur=930, rent_verdict="below_index")
    r = reasons(T, other, 0.84)
    assert r == [
        "Same area · 0.8 km away",
        "2.5 rooms, 48 m² (this: 2 rooms, 50 m²)",
        "€70 less warm",
        "Fair rent",
    ]
    r2 = reasons(T, flat("p", planning_area="B", warm_eur=1005, rooms=1, size_m2=30), 1.26)
    assert r2[0] == "Same district · 1.3 km away"
    assert r2[1].startswith("1 room, 30 m²")
    assert r2[2] == "About the same warm rent"
    assert reasons(T, flat("q", planning_area="X", district="Pankow", warm_eur=1200), 4.0)[
        :3:2
    ] == ["4.0 km away", "€200 more warm"]


# --- API (demo mode, no network) -------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    def no_network(*a, **kw):
        raise AssertionError(f"network access attempted in demo mode: {a}")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(settings, "wohniq_demo", True)
    app.dependency_overrides.clear()
    return TestClient(app)


def test_similar_endpoint_returns_explained_cards_with_risk(client):
    repo = get_demo_repository()
    lid = str(next(iter(repo._listings)))
    resp = client.get(f"/api/v1/listings/{lid}/similar")
    assert resp.status_code == 200
    body = resp.json()
    items = body["items"]
    assert 6 <= len(items) <= 12
    ids = [i["listing"]["id"] for i in items]
    assert lid not in ids and len(set(ids)) == len(ids)
    for i in items:
        assert i["reasons"] and "km away" in i["reasons"][0]
        assert 0 <= i["score"] <= 1
        assert i["risk"] is None or i["risk"]["band"] in {"low", "caution", "high"}
    scores = [i["score"] for i in items]
    if not body["within_limit_first"]:
        assert scores == sorted(scores, reverse=True)
    assert client.get(f"/api/v1/listings/{lid}/similar").json() == body  # deterministic


def test_similar_includes_high_risk_listings_somewhere(client):
    repo = get_demo_repository()
    listings = list(repo._listings.values())
    risk = repo.risk_by_listing([x.id for x in listings])
    high = [x for x in listings if (r := risk.get(str(x.id))) and r.band == "high"]
    assert high
    seen = False
    for x in listings[:60]:
        items = client.get(f"/api/v1/listings/{x.id}/similar").json()["items"]
        if any(i["risk"] and i["risk"]["band"] == "high" for i in items):
            seen = True
            break
    assert seen


def test_similar_unknown_and_bad_ids(client):
    assert client.get("/api/v1/listings/not-a-uuid/similar").status_code == 400
    assert (
        client.get("/api/v1/listings/00000000-0000-0000-0000-000000000000/similar").status_code
        == 404
    )


def test_listing_location_carries_the_matched_address_id(client):
    """ "Check this rent" opens the rent check at the listing's matched address (T9.7)."""
    repo = get_demo_repository()
    lid = str(next(iter(repo._listings)))
    loc = client.get(f"/api/v1/listings/{lid}").json()["location"]
    assert isinstance(loc["address_id"], int)
    addr = client.get(f"/api/v1/rent/addresses/{loc['address_id']}").json()
    assert addr["street"] == loc["street"] and addr["postcode"] == loc["postcode"]
