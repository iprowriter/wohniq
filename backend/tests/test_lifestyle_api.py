"""Endpoint tests for /api/v1/lifestyle (T7.3). Pure data + FakeRepository; no DB, no network."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repository import get_repository
from data.models import Listing
from lifestyle.profiles import get_bundle
from lifestyle.shapes import get_shapes
from tests.fake_repository import FakeRepository

client = TestClient(app)
API = "/api/v1/lifestyle"


@pytest.fixture(scope="module")
def catalog():
    return client.get(f"{API}/catalog").json()


@pytest.fixture(scope="module")
def student(catalog):
    return next(p for p in catalog["presets"] if p["id"] == "student")["answers"]


# --- catalog / shapes -------------------------------------------------------------------


def test_catalog(catalog):
    r = client.get(f"{API}/catalog")
    assert r.status_code == 200
    assert r.headers["cache-control"].startswith("public")  # static, no user data
    assert [p["id"] for p in catalog["pages"]] == ["move", "days", "free_time", "neighbourhood"]
    assert len(catalog["presets"]) == 5 and len(catalog["destinations"]) == 13
    assert catalog["region_count"] == 143
    assert all(q["options"] for q in catalog["questions"])  # only fixed choices, no free text
    assert all(a["available"] for a in catalog["attributes"])
    assert "not stored" in catalog["privacy"]
    evenings = next(q for q in catalog["questions"] if q["id"] == "evenings")
    assert {"nightlife": 5} in [o["sets"] for o in evenings["options"]]  # transparent mapping


def test_regions_geojson():
    r = client.get(f"{API}/regions.geojson")
    assert r.status_code == 200 and r.headers["cache-control"].startswith("public")
    keys = {f["properties"]["key"] for f in r.json()["features"]}
    assert keys == {reg.key for reg in get_bundle().regions}


# --- profile ----------------------------------------------------------------------------


def test_profile_for_the_student_preset(student):
    r = client.post(f"{API}/profile", json={"answers": student})
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["persona"]["id"] == "campus_explorer"
    weights = {w["attribute"]: w["value"] for w in body["weights"]}
    assert weights["commute"] == 5 and weights["affordability"] == 5
    commute = next(w for w in body["weights"] if w["attribute"] == "commute")
    assert commute["reasons"] == ["How often do you go there? → Every day"]
    choices = {c["question"]: c["answer"] for c in body["choices"]}
    assert choices["Budget (warm)"] == "€700 per month"
    assert choices["Flat"] == "30 m², 1 room"
    assert "TU Berlin" in choices["Where you go most"]


def test_profile_overrides_and_validation(student):
    r = client.post(f"{API}/profile", json={"answers": student, "weights": {"nightlife": 0}})
    nightlife = next(w for w in r.json()["weights"] if w["attribute"] == "nightlife")
    assert nightlife == {
        "attribute": "nightlife",
        "label": "Nightlife",
        "value": 0,
        "reasons": ["Set by you"],
        "overridden": True,
    }
    assert (
        client.post(
            f"{API}/profile", json={"answers": student, "weights": {"vibes": 2}}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API}/profile", json={"answers": student, "weights": {"water": 9}}
        ).status_code
        == 422
    )
    assert (
        client.post(f"{API}/profile", json={"answers": {**student, "name": "A"}}).status_code == 422
    )
    assert (
        client.post(f"{API}/profile", json={"answers": student, "email": "a@b"}).status_code == 422
    )


# --- match ------------------------------------------------------------------------------


def test_match_student(student):
    r = client.post(f"{API}/match", json={"answers": student, "limit": 5})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["total_regions"] == 143 and len(body["results"]) == 5
    top = body["results"][0]
    assert top["rank"] == 1 and top["fits_budget"] and top["commute"]["minutes"] <= 30
    assert top["reasons"] and top["evidence"] and top["factors"]
    assert any("district median" in n for n in top["notes"])  # data caveat, not a trade-off
    assert not any("district median" in c for c in top["caveats"])
    assert all(
        e["source_id"] in {s["id"] for s in client.get(f"{API}/catalog").json()["sources"]}
        for e in top["evidence"]
    )
    assert body["persona"]["id"] == "campus_explorer"


def test_match_returns_compact_scores_for_every_region(student):
    body = client.post(f"{API}/match", json={"answers": student, "limit": 3}).json()
    assert len(body["results"]) == 3 and len(body["scores"]) == 143
    assert [s["rank"] for s in body["scores"]] == list(range(1, 144))
    top = body["results"][0]
    assert body["scores"][0] == {
        "key": top["key"],
        "rank": 1,
        "score": top["score"],
        "fits_budget": top["fits_budget"],
        "within_commute": top["within_commute"],
    }
    excluded = client.post(
        f"{API}/match", json={"answers": student, "limit": 3, "excluded": [top["key"]]}
    ).json()
    assert len(excluded["scores"]) == 142 and top["key"] not in {
        s["key"] for s in excluded["scores"]
    }


def test_match_exclusion_and_overrides(student):
    full = client.post(f"{API}/match", json={"answers": student, "limit": 143}).json()["results"]
    scores = {x["key"]: x["score"] for x in full}
    drop = [full[0]["key"], full[1]["key"]]
    r = client.post(f"{API}/match", json={"answers": student, "limit": 143, "excluded": drop})
    rest = r.json()["results"]
    assert len(rest) == 141 and not set(drop) & {x["key"] for x in rest}
    assert all(scores[x["key"]] == x["score"] for x in rest)
    assert r.json()["excluded"] == sorted(drop)


@pytest.mark.parametrize(
    "patch, status",
    [
        ({"excluded": ["999999"]}, 422),
        ({"answers_patch": {"destination": "mars"}}, 422),
        ({"limit": 0}, 422),
        ({"weights": {"commute": 6}}, 422),
    ],
)
def test_match_rejects_bad_requests(student, patch, status):
    body = {"answers": {**student, **patch.pop("answers_patch", {})}, **patch}
    assert client.post(f"{API}/match", json=body).status_code == status


def test_match_needs_a_scorable_weight():
    answers = {"budget_eur": 900, "size_m2": 40}  # nothing chosen -> all weights 0
    r = client.post(f"{API}/match", json={"answers": answers})
    assert r.status_code == 422 and "at least one" in r.json()["detail"]


def test_match_reports_unscored_commute_without_destination():
    answers = {"budget_eur": 900, "size_m2": 40, "frequency": "daily", "evenings": "out_often"}
    r = client.post(f"{API}/match", json={"answers": answers, "weights": {"commute": 5}})
    assert r.status_code == 200 and "commute" in r.json()["unscored"]


# --- listings hand-off ---------------------------------------------------------------------


def _listing(lat, lng, warm, rooms=1.0):
    x = Listing()
    x.id = uuid.uuid4()
    x.title, x.address, x.kiez, x.district = "Flat", "Str. 1, Berlin", "Charlottenburg", None
    x.lat, x.lng, x.rooms, x.size_m2 = lat, lng, rooms, 30
    x.kaltmiete_eur, x.nebenkosten_eur, x.warmmiete_eur = warm - 100, 100, warm
    x.deposit_eur, x.furnished, x.available_from = None, False, None
    x.photo_set_id = uuid.uuid4()
    x.is_scam, x.scam_type = True, "price_bait"  # must never be serialized
    return x


def test_listings_are_matched_by_coordinates_not_labels():
    bundle = get_bundle()
    region = next(r for r in bundle.regions if r.name == "Otto-Suhr-Allee/Kantstraße")
    lat, lng = region.centroid
    assert get_shapes().region_of(lat, lng) == region.key
    inside_cheap = _listing(lat, lng, 650)
    inside_dear = _listing(lat + 0.0005, lng, 900, rooms=2)
    outside = _listing(52.45, 13.60, 500)  # Köpenick, though labelled "Charlottenburg"
    repo = FakeRepository([inside_dear, inside_cheap, outside])
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        r = client.post(f"{API}/listings", json={"region_key": region.key, "budget_eur": 700})
        rooms = client.post(f"{API}/listings", json={"region_key": region.key, "min_rooms": 2})
        missing = client.post(f"{API}/listings", json={"region_key": "999999"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["count"] == 2 and body["region_name"] == region.name
    assert [x["listing"]["id"] for x in body["listings"]] == [
        str(inside_cheap.id),
        str(inside_dear.id),
    ]
    assert [x["fits_budget"] for x in body["listings"]] == [True, False]
    assert (
        "is_scam" not in body["listings"][0]["listing"]
        and "scam_type" not in body["listings"][0]["listing"]
    )
    assert rooms.json()["count"] == 1
    assert missing.status_code == 404


def test_listings_in_the_offline_demo_use_real_coordinates():
    """Demo inventory: exactly the listings located in the region, whatever their label."""
    from data.demo_repository import get_demo_repository

    demo = get_demo_repository()
    app.dependency_overrides[get_repository] = lambda: demo
    try:
        shapes = get_shapes()
        all_listings = demo.listings_in_bbox(52.3, 13.0, 52.7, 13.8)
        for region in get_bundle().regions:
            if region.listing_kiez not in ("Charlottenburg", "Treptow", "Mitte"):
                continue
            expected = {
                str(x.id) for x in all_listings if shapes.shapes[region.key].contains(x.lat, x.lng)
            }
            r = client.post(f"{API}/listings", json={"region_key": region.key, "limit": 50})
            assert r.status_code == 200
            assert {x["listing"]["id"] for x in r.json()["listings"]} == expected
            assert r.json()["count"] == len(expected)
    finally:
        app.dependency_overrides.clear()


def test_frontend_catalog_fixture_is_current():
    """Frontend tests read this fixture; refresh with `make lifestyle-fixture`."""
    import json

    from data.lifestyle.export_catalog import FIXTURE, catalog_json

    assert FIXTURE.is_file(), "run `make lifestyle-fixture`"
    assert (
        json.loads(FIXTURE.read_text(encoding="utf-8")) == catalog_json()
    ), "frontend/tests/fixtures/lifestyle-catalog.json is stale — run `make lifestyle-fixture`"
