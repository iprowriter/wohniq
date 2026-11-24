"""/api/v1/listings/map — every listing as a map point (homepage "See on the map")."""

import socket
import statistics

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.config import settings
from data.demo_repository import get_demo_repository
from data.kieze import BERLIN_BBOX


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


def test_map_returns_every_listing_with_card_details(client):
    resp = client.get("/api/v1/listings/map")
    assert resp.status_code == 200  # not swallowed by /listings/{listing_id}
    points = resp.json()
    repo = get_demo_repository()
    assert len(points) == len(repo._listings) == 140
    assert len({p["id"] for p in points}) == 140
    for p in points:
        assert BERLIN_BBOX["lat_min"] <= p["lat"] <= BERLIN_BBOX["lat_max"]
        assert BERLIN_BBOX["lng_min"] <= p["lng"] <= BERLIN_BBOX["lng_max"]
        assert p["warmmiete_eur"] > 0 and p["size_m2"] > 0 and p["rooms"] > 0
        assert p["kiez"] and p["district"] and p["title"]
        assert p["photo_url"]  # every demo listing has a photo set
        assert p["risk_band"] in {"low", "caution", "high"}
        assert "is_scam" not in p and "scam_type" not in p


def test_map_prices_match_the_listings(client):
    points = client.get("/api/v1/listings/map").json()
    repo = get_demo_repository()
    for p in points[:10]:
        listing = next(x for x in repo._listings.values() if str(x.id) == p["id"])
        assert p["warmmiete_eur"] == listing.warmmiete_eur
        assert (p["lat"], p["lng"]) == (listing.lat, listing.lng)
    # Sanity for the map's Berlin median bubble.
    median = statistics.median(p["warmmiete_eur"] for p in points)
    assert 500 < median < 2000
