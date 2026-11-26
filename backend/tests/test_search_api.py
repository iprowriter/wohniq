"""Endpoint test for /api/v1/search.

Monkeypatches the LLM steps (parse, explain) and overrides the repository (retrieval +
enrichment), so it verifies the *wiring* — pipeline order, ranking applied, response
shape, and that is_scam never leaks — without network or a database. Ranking runs
for real (it's pure). Runs locally (needs FastAPI/SQLAlchemy).
"""

import uuid

from fastapi.testclient import TestClient

import app.routers.search as search_mod
from app.main import app
from app.repository import get_repository
from data.models import Listing
from search.criteria import SearchCriteria
from search.retrieval import RetrievalResult
from tests.fake_repository import FakeRepository


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


def test_search_pipeline_wiring(monkeypatch):
    good = _listing("Great flat in Mitte", "Mitte", 1100)
    meh = _listing("Pricey flat in Mitte", "Mitte", 1480)

    monkeypatch.setattr(
        search_mod, "parse_query",
        lambda text, **kw: SearchCriteria(max_warm_rent=1500, quiet_priority=True),
    )
    def no_llm(*a, **kw):
        raise AssertionError("/search must not wait for model explanations (ADR-0022)")

    monkeypatch.setattr(search_mod, "explain", no_llm)
    monkeypatch.setattr(search_mod, "explain_many", no_llm)
    # The fake repository returns no enrichment/photos, so those factors stay inactive.
    repo = FakeRepository(retrieval=[RetrievalResult(good, 0.1), RetrievalResult(meh, 0.5)])
    app.dependency_overrides[get_repository] = lambda: repo
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
    # The rule-based explanation, from the same breakdown; the model's comes separately.
    assert first["explanation"]["summary"] and first["explanation"]["reasons"]
    assert isinstance(first["score"], float)
    assert any(f["name"] == "budget" for f in first["factors"])
    # ground-truth labels must never be serialized
    assert "is_scam" not in first["listing"]
    assert "scam_type" not in first["listing"]


def test_commute_note_cases():
    from enrich.commute_parse import CommuteResult

    live = CommuteResult(minutes=20, changes=1, walk_minutes=5)
    est = CommuteResult(minutes=25, changes=None, walk_minutes=None, source="distance")
    note = search_mod._commute_note
    assert note(None, [est]) is None  # no work location asked for
    assert note("Alexanderplatz", [live, live]) is None  # all live: nothing to explain
    assert "estimates" in note("Alexanderplatz", [live, est])
    assert note("Narnia", [None, None]).startswith('Couldn\'t find "Narnia"')


# --- /search/explanations (ADR-0022) ---------------------------------------------------


def _live_llm(monkeypatch, transport):
    """Live mode (not demo) with a fake Gemini transport; no database is touched."""
    import core.llm as llm
    from core.config import settings

    monkeypatch.setattr(settings, "wohniq_demo", False)
    monkeypatch.setattr(settings, "database_url", "postgresql://not-used")
    monkeypatch.setattr(llm, "_call_gemini", transport)


def _explain_body(listings):
    return {
        "criteria": {"max_warm_rent": 1500, "quiet_priority": True},
        "items": [
            {
                "listing_id": str(x.id),
                "score": 0.8,
                "factors": [
                    {
                        "name": "budget",
                        "score": 0.9,
                        "weight": 2,
                        "detail": f"€{x.warmmiete_eur} warm, under your €1.500 budget",
                        "highlight": "under budget",
                    },
                ],
            }
            for x in listings
        ],
    }


def test_explanations_endpoint_batches_and_keeps_rules_for_bad_items(monkeypatch):
    import json

    from core.llm import RawResponse

    a, b, c = (_listing(f"Flat {i}", "Mitte", 1000 + i) for i in range(3))
    calls = []

    def transport(system, user, schema, temperature):
        calls.append(user)
        assert "Listing #1" in user and "Listing #3" in user
        good = "In Mitte, €1.000 warm, under your €1.500 budget."
        generic = "A strong match for your search."  # fails Explanation validation
        items = [
            {"ref": 1, "summary": good, "reasons": ["€1000 warm"], "caveats": []},
            {"ref": 2, "summary": generic, "reasons": [], "caveats": []},
            {"ref": 9, "summary": "Unknown ref.", "reasons": [], "caveats": []},
        ]
        return RawResponse(json.dumps({"items": items}))

    _live_llm(monkeypatch, transport)
    app.dependency_overrides[get_repository] = lambda: FakeRepository(listings=[a, b, c])
    try:
        client = TestClient(app)
        resp = client.post("/api/v1/search/explanations", json=_explain_body([a, b, c]))
        again = client.post("/api/v1/search/explanations", json=_explain_body([a]))
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(calls) == 1  # one call for the whole page
    assert [i["listing_id"] for i in items] == [str(a.id), str(b.id), str(c.id)]
    assert [i["source"] for i in items] == ["ai", "rules", "rules"]
    assert items[0]["explanation"]["summary"].startswith("In Mitte")
    assert items[1]["explanation"]["summary"]  # template, never empty
    # The same input again comes from the cache: no new call.
    assert again.json()["items"][0]["source"] == "ai" and len(calls) == 1


def test_explanations_endpoint_falls_back_when_the_service_fails(monkeypatch):
    def broken(*a, **kw):
        raise RuntimeError("404 model retired")

    a = _listing("Flat", "Mitte", 1100)
    _live_llm(monkeypatch, broken)
    app.dependency_overrides[get_repository] = lambda: FakeRepository(listings=[a])
    try:
        resp = TestClient(app).post("/api/v1/search/explanations", json=_explain_body([a]))
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["items"][0]["source"] == "rules"


def test_explanations_endpoint_rejects_bad_input():
    client = TestClient(app)
    empty = {"criteria": {}, "items": []}
    assert client.post("/api/v1/search/explanations", json=empty).status_code == 422
    body = _explain_body([_listing("Flat", "Mitte", 1100)])
    body["items"][0]["listing_id"] = "not-a-uuid"
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    try:
        assert client.post("/api/v1/search/explanations", json=body).status_code == 400
    finally:
        app.dependency_overrides.clear()
