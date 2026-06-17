"""Endpoint test for /api/v1/search.

Monkeypatches the LLM/DB-touching steps (parse, retrieve, explain) and overrides the
session, so it verifies the *wiring* — pipeline order, ranking applied, response
shape, and that is_scam never leaks — without network or a database. Ranking runs
for real (it's pure). Runs locally (needs FastAPI/SQLAlchemy).
"""

import uuid

import app.routers.search as search_mod
from app.main import app
from core.db import get_session
from data.models import Listing
from fastapi.testclient import TestClient
from search.criteria import SearchCriteria
from search.explanation import Explanation
from search.retrieval import RetrievalResult


def _listing(title, kiez, warm, rooms=2):
    listing = Listing()
    listing.id = uuid.uuid4()
    listing.title = title
    listing.address = "Some Straße 1, 10115 Berlin"
    listing.kiez = kiez
    listing.district = "Mitte"
    listing.rooms = rooms
    listing.size_m2 = 60
    listing.kaltmiete_eur = warm - 300
    listing.nebenkosten_eur = 300
    listing.warmmiete_eur = warm  # DB-computed normally; set directly for the test
    listing.deposit_eur = (warm - 300) * 3
    listing.furnished = False
    listing.available_from = None
    listing.photo_set_id = uuid.uuid4()
    listing.is_scam = True  # should NEVER appear in the response
    listing.scam_type = "price_bait"
    return listing


class _FakeSession:
    def scalars(self, stmt):
        return []  # no photos in this test


def test_search_pipeline_wiring(monkeypatch):
    good = _listing("Great flat in Mitte", "Mitte", 1100)
    meh = _listing("Pricey flat in Mitte", "Mitte", 1480)

    monkeypatch.setattr(
        search_mod, "parse_query",
        lambda text, **kw: SearchCriteria(max_warm_rent=1500, quiet_priority=True),
    )
    monkeypatch.setattr(
        search_mod, "retrieve",
        lambda *a, **kw: [RetrievalResult(good, 0.1), RetrievalResult(meh, 0.5)],
    )
    monkeypatch.setattr(
        search_mod, "explain",
        lambda result, **kw: Explanation(summary="Fits well.", reasons=["€400 under budget"], caveats=[]),
    )
    app.dependency_overrides[get_session] = lambda: _FakeSession()
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/search", json={"query": "quiet flat in Mitte under 1500", "limit": 5})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["criteria"]["max_warm_rent"] == 1500
    assert [r["listing"]["title"] for r in data["results"]] == [
        "Great flat in Mitte",
        "Pricey flat in Mitte",
    ]  # better candidate ranked first
    first = data["results"][0]
    assert first["explanation"]["summary"] == "Fits well."
    assert isinstance(first["score"], float)
    assert any(f["name"] == "budget" for f in first["factors"])
    # ground-truth labels must never be serialized
    assert "is_scam" not in first["listing"]
    assert "scam_type" not in first["listing"]
