"""Endpoint test for /api/v1/compare (stubbed LLM, fake repository)."""

import uuid

import app.routers.search as search_mod
from app.main import app
from app.repository import get_repository
from data.models import Listing
from fastapi.testclient import TestClient
from search.criteria import SearchCriteria
from search.explanation import Explanation
from tests.fake_repository import FakeRepository


def _listing(title, warm, rooms=2):
    x = Listing()
    x.id = uuid.uuid4()
    x.title = title
    x.address = "Straße 1"
    x.kiez = "Mitte"
    x.district = "Mitte"
    x.rooms = rooms
    x.size_m2 = 60
    x.kaltmiete_eur = warm - 300
    x.nebenkosten_eur = 300
    x.warmmiete_eur = warm
    x.deposit_eur = (warm - 300) * 3
    x.furnished = False
    x.available_from = None
    x.photo_set_id = uuid.uuid4()
    x.is_scam = True  # must not leak
    x.scam_type = "price_bait"
    return x


def test_compare_two_listings(monkeypatch):
    a, b = _listing("Flat A", 1100), _listing("Flat B", 1450)

    monkeypatch.setattr(search_mod, "parse_query", lambda text, **kw: SearchCriteria(max_warm_rent=1500))
    monkeypatch.setattr(
        search_mod, "explain",
        lambda result, **kw: Explanation(summary="ok", reasons=["under budget"], caveats=[]),
    )
    app.dependency_overrides[get_repository] = lambda: FakeRepository([a, b])
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/compare",
            json={"listing_ids": [str(a.id), str(b.id)], "query": "flat under 1500"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert [i["listing"]["title"] for i in data["items"]] == ["Flat A", "Flat B"]  # order preserved
    first = data["items"][0]
    assert first["fit_score"] is not None
    assert any(f["name"] == "budget" for f in first["factors"])
    assert "is_scam" not in first["listing"]


def test_compare_rejects_single_listing():
    # FastAPI resolves dependencies before reporting body validation errors,
    # so the repository must be faked even though the request never reaches it.
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/compare", json={"listing_ids": [str(uuid.uuid4())]})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 422  # min_length=2 violated


def test_compare_missing_listing_404(monkeypatch):
    monkeypatch.setattr(search_mod, "parse_query", lambda text, **kw: SearchCriteria())
    app.dependency_overrides[get_repository] = lambda: FakeRepository()  # none found
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/compare",
            json={"listing_ids": [str(uuid.uuid4()), str(uuid.uuid4())]},
        )
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 404
