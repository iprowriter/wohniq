"""Endpoint tests for /api/v1/neighborhoods (M8). Bundle only — no DB, no network."""

import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.neighborhoods import parse_weights
from neighborhoods.catalog import CATEGORIES

client = TestClient(app)
API = "/api/v1/neighborhoods"


@pytest.fixture(scope="module")
def catalog():
    return client.get(f"{API}/catalog").json()


def _ranking(**params):
    r = client.get(f"{API}/ranking", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# --- catalog ------------------------------------------------------------------------------


def test_catalog_lists_categories_metrics_and_sources(catalog):
    r = client.get(f"{API}/catalog")
    assert r.status_code == 200 and r.headers["cache-control"].startswith("public")
    assert [c["id"] for c in catalog["categories"]] == [c.id for c in CATEGORIES]
    assert catalog["area_count"] == 143 and catalog["max_weight"] == 3
    assert len(catalog["districts"]) == 12
    source_ids = {s["id"] for s in catalog["sources"]}
    for c in catalog["categories"]:
        assert c["metrics"] and c["caveat"]
        for m in c["metrics"]:
            if m["available"]:
                assert m["berlin_text"] and m["requires"] is None
            else:
                assert m["requires"]  # pending metrics say what's missing
    assert {"pks_kriminalitaetsatlas", "unfallatlas_2025", "mss_2023"} <= source_ids


def test_catalog_marks_income_pending_with_the_berlin_wide_figure(catalog):
    affluence = next(c for c in catalog["categories"] if c["id"] == "affluence")
    pending = [m for m in affluence["metrics"] if not m["available"]]
    assert [m["id"] for m in pending] == ["income"]
    income = pending[0]
    assert income["requires"] == "Not published per neighborhood"
    assert income["city_text"] == "€45,161 per taxpayer (2022)"
    assert "2,017,622 taxpayers" in income["city_note"]
    assert income["city_source_id"] == "afs_lohnsteuer_2022"
    land = next(m for m in affluence["metrics"] if m["id"] == "land_value")
    assert land["available"] and land["weight"] > 0
    context = next(m for m in affluence["metrics"] if m["id"] == "land_value_eur")
    assert context["available"] and context["weight"] == 0


# --- ranking --------------------------------------------------------------------------------


def test_overall_ranking_covers_every_area_in_order():
    data = _ranking()
    assert data["category"] == "overall" and data["total"] == 143 == len(data["areas"])
    ranks = [a["rank"] for a in data["areas"]]
    scores = [a["score"] for a in data["areas"]]
    assert ranks == sorted(ranks) and ranks[0] == 1
    assert scores == sorted(scores, reverse=True)
    assert data["weights"]["safety"] == 2  # defaults echoed back
    assert all(a["headline"] is None for a in data["areas"])
    assert {a["tier"] for a in data["areas"]} == {"best", "middle", "worst"}


def test_category_ranking_reorders_and_quotes_the_headline_figure():
    overall = [a["key"] for a in _ranking()["areas"]]
    safety = _ranking(category="safety")
    assert [a["key"] for a in safety["areas"]] != overall
    assert safety["best_label"] == "Lowest crime" and safety["worst_label"] == "Highest crime"
    top = safety["areas"][0]
    assert top["headline"]["metric"] == "crime_kiez"
    assert "per 100,000 residents" in top["headline"]["text"]
    # Lowest crime first: the headline figures rise down the list (mostly; ties aside).
    first, last = safety["areas"][0]["headline"]["raw"], safety["areas"][-1]["headline"]["raw"]
    assert first < last


@pytest.mark.parametrize("category", [c.id for c in CATEGORIES])
def test_every_category_can_be_ranked(category):
    data = _ranking(category=category)
    assert data["total"] == 143 and data["weights"] is None


def test_weights_change_the_overall_order():
    default = [a["key"] for a in _ranking()["areas"]]
    cheap = _ranking(weights="affordability:3,safety:0,affluence:0")
    assert [a["key"] for a in cheap["areas"]] != default
    assert cheap["weights"]["affordability"] == 3 and cheap["weights"]["safety"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"category": "vibes"},
        {"weights": "safety:9"},
        {"weights": "safety"},
        {"weights": "nope:1"},
        {"weights": ",".join(f"{c.id}:0" for c in CATEGORIES)},
        {"category": "safety", "weights": "safety:2"},
    ],
)
def test_bad_ranking_requests_are_422(params):
    r = client.get(f"{API}/ranking", params=params)
    assert r.status_code == 422


def test_parse_weights():
    assert parse_weights(None) is None
    w = parse_weights("safety:3, parking:0")
    assert w["safety"] == 3 and w["parking"] == 0 and w["transit"] == 1


# --- area detail ---------------------------------------------------------------------------------


def test_area_detail_has_every_category_with_sourced_metrics(catalog):
    safety = _ranking(category="safety")["areas"]
    key = safety[0]["key"]
    r = client.get(f"{API}/areas/{key}")
    assert r.status_code == 200
    a = r.json()
    assert a["key"] == key and a["total"] == 143
    assert [c["id"] for c in a["categories"]] == [c.id for c in CATEGORIES]
    cat_safety = next(c for c in a["categories"] if c["id"] == "safety")
    assert cat_safety["rank"] == safety[0]["rank"] and cat_safety["tier_label"] == "Lowest crime"
    source_ids = {s["id"] for s in catalog["sources"]}
    for c in a["categories"]:
        for m in c["metrics"]:
            assert m["source_id"] in source_ids and m["method"] and m["text"]
            assert 0 <= m["score"] <= 100
    assert a["summary"].startswith(f"#{a['overall']['rank']} of 143 overall.")
    assert any(h["category"] == "safety" for h in a["strengths"])


def test_area_overall_rank_matches_the_ranking_for_the_same_weights():
    w = "transit:3,parking:0"
    ranking = _ranking(weights=w)["areas"]
    pick = ranking[10]
    a = client.get(f"{API}/areas/{pick['key']}", params={"weights": w}).json()
    assert a["overall"]["rank"] == pick["rank"]


def test_unknown_area_is_404():
    assert client.get(f"{API}/areas/999999").status_code == 404


def test_regions_geojson_has_143_outlines():
    r = client.get(f"{API}/regions.geojson")
    assert r.status_code == 200
    keys = {f["properties"]["key"] for f in r.json()["features"]}
    assert len(keys) == 143 and keys == {a["key"] for a in _ranking()["areas"]}


def test_ranking_logs_counts_only(caplog):
    with caplog.at_level(logging.INFO):
        _ranking(weights="safety:3")
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "143 areas" in text and "safety:3" not in text


def test_frontend_fixtures_are_fresh():
    from data.neighborhoods.export_fixture import FIXTURES, fixtures, render

    for name, data in fixtures().items():
        path = FIXTURES / name
        assert path.exists() and path.read_text(encoding="utf-8") == render(
            data
        ), f"frontend/tests/fixtures/{name} is stale — run `make neighborhoods-fixture`"
