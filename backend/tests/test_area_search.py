"""Area-aware search: parsing, SQL/Python filter parity, ranking, explanations, notices.

The end-to-end cases run the real pipeline in offline demo mode (keyword parser,
demo repository, deterministic ranking + template explanations) — the same code path
a user hits without Gemini — against the 100 seeded demo listings.
"""

import json
import socket

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text

import app.routers.search as search_mod
from app.main import app
from core.config import settings
from core.llm import RawResponse
from data.demo_repository import DemoRepository, get_demo_repository
from data.models import Listing
from search.areas import matching_area
from search.criteria import SearchCriteria
from search.diagnostics import budget_advice, budget_notice, requirements_phrase
from search.explain_rules import GENERIC_SUMMARY, MatchContext, compose_summary
from search.explanation import template_fallback
from search.parse_rules import extract_criteria
from search.parser import parse_query
from search.ranking import IN_AREA, NEARBY, RankCriteria, RankingInput, score_listing
from search.retrieval import area_conditions

REPORTED_QUERY = "a quiet flat in Mitte, Spandau, Lichtenberg, Treptow"
REPORTED_AREAS = ["Mitte", "Spandau", "Lichtenberg", "Treptow"]


# --- Parsing -------------------------------------------------------------------------


def test_keyword_parser_extracts_areas():
    out = extract_criteria(REPORTED_QUERY)
    assert out["areas"] == REPORTED_AREAS
    assert out["quiet_priority"] is True
    assert out["work_location"] is None


def test_near_an_area_is_where_to_live_not_a_workplace():
    # The homepage placeholder: "quiet 2-room near Mitte" used to set work_location.
    out = extract_criteria("quiet 2-room near Mitte, budget €1,400")
    assert out["areas"] == ["Mitte"] and out["work_location"] is None
    out = extract_criteria("I work in Mitte, flat in Pankow")
    assert out["areas"] == ["Pankow"] and out["work_location"] == "Mitte"
    assert extract_criteria("I work near Kreuzberg")["work_location"] == "Kreuzberg"


@pytest.mark.parametrize(
    "query, workplace",
    [
        ("I teach at a school in Neukölln", "Neukölln"),
        ("my job is in Nkln", "Neukölln"),
        ("I'm a student in P'berg", "Prenzlauer Berg"),
        ("internship in Xberg", "Kreuzberg"),
    ],
)
def test_workplace_from_the_area_scan_uses_the_proper_name(query, workplace):
    from enrich.places import resolve_place

    assert extract_criteria(query)["work_location"] == workplace
    assert resolve_place(workplace) is not None  # so the commute can be calculated


@pytest.mark.parametrize(
    "query, budget",
    [
        ("cheap place under 1000", 1000),
        ("budget 1.5k", 1500),
        ("max 1.2k warm", 1200),
        ("budget €1,500", 1500),
        ("1.500 EUR per month", 1500),
        ("2 rooms under 60m2", None),  # a size, not a budget
    ],
)
def test_budget_formats_used_by_the_budget_hint(query, budget):
    assert extract_criteria(query)["max_warm_rent"] == budget


def _transport(json_text):
    def send(system, user, schema, temperature):
        return RawResponse(text=json_text)

    return send


def test_llm_areas_are_canonicalised_and_merged_with_the_text(monkeypatch):
    # The model returned a nickname and missed one area; the text scan fills the gap.
    raw = '{"quiet_priority": true, "areas": ["P\'berg"], "excluded_areas": []}'
    crit = parse_query("quiet flat in P'berg or Fhain", transport=_transport(raw))
    assert crit.areas == ["Prenzlauer Berg", "Friedrichshain"]


def test_llm_workplace_or_avoided_area_never_becomes_a_living_area():
    raw = '{"work_location": "Mitte", "areas": ["Mitte", "Pankow", "Neukölln"]}'
    crit = parse_query(
        "I work in Mitte, want a flat in Pankow, not Neukölln", transport=_transport(raw)
    )
    assert crit.areas == ["Pankow"]
    assert crit.excluded_areas == ["Neukölln"]
    assert crit.work_location == "Mitte"


# --- Workplace rule: identical for Gemini and the keyword parser ----------------------------


@pytest.mark.parametrize(
    "model_answer",
    [
        {"areas": ["Mitte"]},  # follows parser.v2
        {"work_location": "Mitte", "areas": ["Mitte"]},  # workplace and area
        {"work_location": "Mitte"},  # answers like parser.v1
        {"work_location": "Berlin-Mitte"},  # spelling variant of the same area
    ],
)
def test_near_an_area_is_never_a_workplace_whatever_the_model_says(model_answer):
    crit = parse_query("quiet 2-room near Mitte", transport=_transport(json.dumps(model_answer)))
    assert crit.work_location is None
    assert crit.areas == ["Mitte"]


@pytest.mark.parametrize(
    "query, model_work, expected",
    [
        # the text says it's the workplace -> kept
        ("I work in Mitte, flat in Pankow", "Mitte", "Mitte"),
        ("my office is in Kreuzberg, quiet flat", "Kreuzberg", "Kreuzberg"),
        ("good commute to Mitte, 3 rooms", "Mitte", "Mitte"),
        (
            "I am a student in Charlottenburg, looking for a room",
            "Charlottenburg",
            "Charlottenburg",
        ),
        ("internship at Zalando in Friedrichshain", "Friedrichshain", "Friedrichshain"),
        # landmarks aren't areas -> always kept
        ("I work near Alexanderplatz, budget 1500", "Alexanderplatz", "Alexanderplatz"),
        ("flat near Alexanderplatz", "Alexanderplatz", "Alexanderplatz"),
        # a Berlin area the text doesn't call a workplace -> dropped
        ("quiet 2-room near Mitte", "Mitte", None),
        ("flat near Kreuzberg, 2 rooms", "Kreuzberg", None),
        ("a quiet flat in Pankow", "Pankow", None),
        ("looking for a student room in Mitte", "Mitte", None),
        ("3 rooms for a family near a good school in Pankow", "Pankow", None),
    ],
)
def test_workplace_rule_is_the_same_for_gemini_and_the_keyword_parser(query, model_work, expected):
    crit = parse_query(query, transport=_transport(json.dumps({"work_location": model_work})))
    assert crit.work_location == expected  # Gemini path
    assert extract_criteria(query)["work_location"] == expected  # offline path, same decision


@pytest.mark.parametrize(
    "query, model_answer, work, areas",
    [
        # Gemini missed the workplace the text names -> added (proper name)
        ("doing an internship in Mitte, 1 room", {"min_rooms": 1}, "Mitte", []),
        ("doing an internship in Mitte, 1 room", {"areas": ["Mitte"]}, "Mitte", []),
        ("I work in Mitte, flat in Pankow", {"areas": ["Pankow"]}, "Mitte", ["Pankow"]),
        ("my job is in Nkln", {}, "Neukölln", []),
        # Gemini picked the wrong area -> replaced by the one the text calls the workplace
        (
            "I work in Mitte, flat near Kreuzberg",
            {"work_location": "Kreuzberg"},
            "Mitte",
            ["Kreuzberg"],
        ),
        # Gemini's landmark is kept, not overwritten by the area around it
        (
            "I work near Alexanderplatz in Mitte",
            {"work_location": "Alexanderplatz"},
            "Alexanderplatz",
            [],
        ),
        # nothing in the text is a workplace -> stays empty
        ("quiet flat in Pankow", {}, None, ["Pankow"]),
        # a loose "near X" that isn't an area is left to Gemini's judgement (not added)
        ("flat close to Görlitzer Park", {}, None, []),
    ],
)
def test_workplace_gemini_missed_is_added_from_the_text(query, model_answer, work, areas):
    crit = parse_query(query, transport=_transport(json.dumps(model_answer)))
    assert crit.work_location == work
    assert crit.areas == areas


@pytest.mark.parametrize(
    "query",
    [
        "I work in Mitte, flat in Pankow",
        "my office is in Kreuzberg, quiet flat",
        "good commute to Mitte, 3 rooms",
        "I am a student in Charlottenburg, looking for a room",
        "I teach at a school in Neukölln, flat nearby",
        "internship at Zalando in Friedrichshain",
        "my Ausbildung is in Lichtenberg",
        "I'm a student in P'berg",
    ],
)
def test_workplace_area_is_found_even_if_gemini_returns_nothing(query):
    # Whatever Gemini misses, a workplace *area* ends up the same as offline.
    crit = parse_query(query, transport=_transport("{}"))
    assert crit.work_location is not None
    assert crit.work_location == extract_criteria(query)["work_location"]


def test_criteria_validator_drops_unknown_areas():
    crit = SearchCriteria(areas=["Xberg", "Narnia", "kreuzberg"])
    assert crit.areas == ["Kreuzberg"]


# --- SQL filter == Python filter ------------------------------------------------------------


@pytest.fixture(scope="module")
def demo_listings():
    return list(DemoRepository()._listings.values())


@pytest.fixture(scope="module")
def sqlite_listing_table(demo_listings):
    """A minimal `listing` table (kiez, district) so the real SQL conditions can run."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE listing (title TEXT, kiez TEXT, district TEXT)"))
        conn.execute(
            text("INSERT INTO listing VALUES (:title, :kiez, :district)"),
            [{"title": str(x.id), "kiez": x.kiez, "district": x.district} for x in demo_listings],
        )
    return engine


@pytest.mark.parametrize(
    "areas, excluded",
    [
        (REPORTED_AREAS, []),
        (["Prenzlauer Berg"], []),
        (["Bezirk Mitte"], []),
        (["Kreuzkölln"], []),
        (["Friedrichshain-Kreuzberg", "Pankow"], []),
        ([], ["Neukölln", "Kreuzberg"]),
        (["Friedrichshain-Kreuzberg"], ["Kreuzberg"]),
        (["Köpenick"], []),
    ],
)
def test_sql_area_filter_matches_python_filter(
    sqlite_listing_table, demo_listings, areas, excluded
):
    criteria = SearchCriteria(areas=areas, excluded_areas=excluded)
    stmt = select(Listing.title).where(*area_conditions(criteria))
    with sqlite_listing_table.connect() as conn:
        sql_ids = {row[0] for row in conn.execute(stmt)}

    def python_keeps(x):
        if areas and matching_area(x.kiez, x.district, criteria.areas) is None:
            return False
        return not (excluded and matching_area(x.kiez, x.district, criteria.excluded_areas))

    assert sql_ids == {str(x.id) for x in demo_listings if python_keeps(x)}


# --- Ranking + explanation ---------------------------------------------------------------


def test_area_factor_in_area_vs_nearby():
    crit = RankCriteria(areas=("Mitte",), quiet_priority=True)
    inside = score_listing(
        RankingInput(
            warmmiete_eur=1000,
            kiez="Mitte",
            nightlife="high",
            area_status=IN_AREA,
            area_name="Mitte",
        ),
        crit,
    )
    near = score_listing(
        RankingInput(
            warmmiete_eur=1000,
            kiez="Moabit",
            nightlife="high",
            area_status=NEARBY,
            area_name="Mitte",
            area_distance_km=4.0,
        ),
        crit,
    )
    area_in = next(f for f in inside.factors if f.name == "area")
    area_near = next(f for f in near.factors if f.name == "area")
    assert area_in.score == 1.0 and area_in.detail == "In Mitte, as you asked"
    assert area_near.score < 0.4  # always an honest caveat
    assert "Not in Mitte: Moabit is 4.0 km from Mitte" == area_near.detail
    assert inside.total > near.total


def test_summary_says_why_it_is_a_strong_match():
    crit = RankCriteria(max_warm_rent=1000, quiet_priority=True, areas=("Mitte", "Lichtenberg"))
    result = score_listing(
        RankingInput(
            warmmiete_eur=529,
            kiez="Lichtenberg",
            nightlife="low",
            area_status=IN_AREA,
            area_name="Lichtenberg",
        ),
        crit,
    )
    ctx = MatchContext(kiez="Lichtenberg", rooms=2, size_m2=55, asked_min_rooms=2)
    out = template_fallback(result, ctx)
    assert out.summary == (
        "A strong match: in Lichtenberg, €471 under your €1.000 budget and a quiet Kiez "
        "with little nightlife."
    )
    assert "In Lichtenberg, one of the areas you asked for" in out.reasons
    assert "€529 warm, €471 under your €1.000 budget" in out.reasons
    assert "2 rooms, you asked for 2+" in out.reasons
    assert out.caveats == []


def test_summary_admits_the_main_trade_off():
    crit = RankCriteria(quiet_priority=True, areas=("Mitte",))
    result = score_listing(
        RankingInput(
            warmmiete_eur=1300,
            kiez="Mitte",
            nightlife="high",
            area_status=IN_AREA,
            area_name="Mitte",
        ),
        crit,
    )
    summary = template_fallback(result).summary
    assert summary.endswith("but Mitte is lively, with lots of nightlife.")
    assert "in Mitte as you asked" in summary


def test_generic_summaries_are_rejected_and_never_produced():
    for generic in ["A strong match for your search.", "A solid fit.", "Strong match"]:
        assert GENERIC_SUMMARY.match(generic)
    assert not GENERIC_SUMMARY.match("A strong match: in Mitte as you asked.")
    assert not GENERIC_SUMMARY.match(compose_summary(0.9, [], None))


def test_llm_generic_summary_triggers_the_template():
    from search.explanation import explain

    result = score_listing(RankingInput(warmmiete_eur=900), RankCriteria(max_warm_rent=1000))
    generic = '{"summary": "A strong match for your search.", "reasons": [], "caveats": []}'
    out = explain(result, transport=_transport(generic))
    assert out.summary.startswith("A strong match: €100 under your €1.000 budget")


# --- Budget diagnostics --------------------------------------------------------------------


def test_budget_advice_recommends_minimum_and_comfortable_budget():
    advice = budget_advice(600, [1010, 1162, 1269, 1284, 2201])
    assert advice.suggested_budget == 1010
    assert advice.options_at_suggested == 1
    assert advice.comfortable_budget == 1300 and advice.options_at_comfortable == 4
    notice = budget_notice(advice, ["Mitte"], requirements_phrase(2, None, None))
    assert notice.kind == "budget_too_low"
    assert "No flats in Mitte with 2+ rooms fit a budget of €600 warm" in notice.message
    assert "at least €1.010" in notice.message


def test_budget_advice_only_when_budget_is_the_blocker():
    assert budget_advice(1200, [1010, 1500]) is None  # something fits
    assert budget_advice(None, [1010]) is None
    assert budget_advice(600, []) is None  # nothing to recommend


# --- End to end (offline demo mode) ---------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """Offline demo mode with the network blocked (same setup as test_demo_mode)."""

    def no_network(*a, **kw):
        raise AssertionError(f"network access attempted in demo mode: {a}")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    monkeypatch.setattr(settings, "wohniq_demo", True)
    app.dependency_overrides.clear()
    return TestClient(app)


def _search(client, query, **extra):
    resp = client.post("/api/v1/search", json={"query": query, "limit": 6, **extra})
    assert resp.status_code == 200
    return resp.json()


def test_reported_query_only_returns_the_requested_districts(client):
    data = _search(client, REPORTED_QUERY)
    assert data["criteria"]["areas"] == REPORTED_AREAS
    assert data["results"]
    for item in data["results"]:
        assert item["listing"]["kiez"] in REPORTED_AREAS
        assert item["area_match"]["status"] == "in_area"
        summary = item["explanation"]["summary"]
        assert not GENERIC_SUMMARY.match(summary)
        assert item["listing"]["kiez"] in summary  # says where, not just "strong match"


@pytest.mark.parametrize(
    "query, expected_kieze",
    [
        ("quiet apartment in Prenzlauerberg", {"Prenzlauer Berg"}),
        ("a quiet flat in Mitte", {"Mitte"}),
        ("flat in Xberg or Friedrichshain, budget 1400", {"Kreuzberg", "Friedrichshain"}),
        ("2 rooms in Kreuzkölln", {"Neukölln", "Kreuzberg"}),
        ("flat in Bezirk Mitte", {"Mitte", "Moabit", "Wedding"}),
    ],
)
def test_results_never_leave_the_requested_areas(client, query, expected_kieze):
    data = _search(client, query)
    assert data["results"]
    assert {r["listing"]["kiez"] for r in data["results"]} <= expected_kieze
    assert data["notices"] == []


def test_gemini_reading_near_mitte_as_a_workplace_adds_no_commute(client, monkeypatch):
    # Gemini answering like parser.v1 ("near Mitte" = workplace) gets the same result as
    # the offline parser: Mitte is where to live, and there's no commute to it.
    answer = json.dumps({"quiet_priority": True, "min_rooms": 2, "work_location": "Mitte"})
    monkeypatch.setattr(
        search_mod,
        "parse_query",
        lambda text, **kw: parse_query(text, transport=_transport(answer)),
    )
    data = _search(client, "quiet 2-room near Mitte")
    assert data["criteria"]["work_location"] is None
    assert data["criteria"]["areas"] == ["Mitte"]
    assert data["commute_note"] is None
    assert data["results"]
    assert all(r["commute"] is None for r in data["results"])
    assert all(r["listing"]["kiez"] == "Mitte" for r in data["results"])


def test_gemini_missing_the_workplace_still_gets_commute_times(client, monkeypatch):
    # Gemini returns the area to live in but forgets the workplace: commute is still shown.
    answer = json.dumps({"areas": ["Pankow"]})
    monkeypatch.setattr(
        search_mod,
        "parse_query",
        lambda text, **kw: parse_query(text, transport=_transport(answer)),
    )
    data = _search(client, "I work in Mitte, flat in Pankow")
    assert data["criteria"]["work_location"] == "Mitte"
    assert data["criteria"]["areas"] == ["Pankow"]
    assert data["results"]
    assert all(r["listing"]["kiez"] == "Pankow" for r in data["results"])
    assert all(r["commute"] is not None for r in data["results"])
    assert "Mitte" in data["commute_note"]


def test_excluded_areas_never_appear(client):
    data = _search(client, "anywhere but Neukölln or Kreuzberg", limit=20)
    assert data["results"]
    assert not {r["listing"]["kiez"] for r in data["results"]} & {"Neukölln", "Kreuzberg"}


def test_no_listings_in_area_shows_labelled_nearby_flats(client):
    data = _search(client, "flat in Wilmersdorf")
    assert [n["kind"] for n in data["notices"]] == ["nearby_results"]
    assert "Wilmersdorf" in data["notices"][0]["title"]
    assert data["results"]
    for item in data["results"]:
        match = item["area_match"]
        assert match["status"] == "nearby" and match["area"] == "Wilmersdorf"
        assert 0 < match["distance_km"] <= 6
        assert any("Not in Wilmersdorf" in c for c in item["explanation"]["caveats"])
    distances = [r["area_match"]["distance_km"] for r in data["results"]]
    assert distances[0] == min(distances)


def test_nothing_nearby_points_to_the_closest_area(client):
    data = _search(client, "flat in Köpenick, 2 rooms")
    assert data["results"] == []
    [notice] = data["notices"]
    assert notice["kind"] == "no_results"
    assert "The closest matching flats are in Treptow" in notice["message"]


def test_budget_too_low_explains_and_recommends_a_minimum(client):
    data = _search(client, "quiet flat in Mitte budget €300")
    assert data["results"] == []
    [notice] = data["notices"]
    assert notice["kind"] == "budget_too_low"
    assert "€300" in notice["message"] and "Mitte" in notice["message"]
    suggested = notice["suggested_budget"]
    assert suggested and suggested > 300

    # Following the advice (budget override from the UI) really shows flats in Mitte.
    data = _search(client, "quiet flat in Mitte budget €300", max_warm_rent=suggested)
    assert data["criteria"]["max_warm_rent"] == suggested
    assert data["results"] and data["notices"] == []
    assert all(r["listing"]["kiez"] == "Mitte" for r in data["results"])
    assert all(r["listing"]["warmmiete_eur"] <= suggested for r in data["results"])


def test_budget_too_low_citywide(client):
    data = _search(client, "any flat, budget 200")
    [notice] = data["notices"]
    assert notice["kind"] == "budget_too_low" and "in Berlin" in notice["message"]
    cheapest = min(x.warmmiete_eur for x in get_demo_repository()._listings.values())
    assert notice["suggested_budget"] >= cheapest


def test_budget_blocking_one_of_several_areas_is_reported(client):
    data = _search(client, REPORTED_QUERY + ", budget 1000")
    assert data["results"]
    kinds = [n["kind"] for n in data["notices"]]
    assert kinds == ["budget_too_low_in_some_areas"]
    assert "Mitte" in data["notices"][0]["message"]


def test_high_risk_listings_never_set_the_recommended_budget(client, monkeypatch):
    repo = get_demo_repository()
    mitte = sorted(
        (x for x in repo._listings.values() if x.kiez == "Mitte"), key=lambda x: x.warmmiete_eur
    )
    cheapest, second = mitte[0], mitte[1]
    real = repo.risk_by_listing

    def risk_with_cheapest_high(ids):
        out = real(ids)
        if str(cheapest.id) in out:
            row = out[str(cheapest.id)]
            out[str(cheapest.id)] = type(row)(
                listing_id=row.listing_id, score=90, band="high", signals=[]
            )
        return out

    monkeypatch.setattr(repo, "risk_by_listing", risk_with_cheapest_high)
    data = _search(client, "flat in Mitte, budget 300")
    assert data["notices"][0]["suggested_budget"] >= second.warmmiete_eur


def test_search_wiring_passes_area_into_ranking(monkeypatch, client):
    # Parsed areas reach ranking: every factor list carries an "area" factor.
    data = _search(client, "flat in Spandau")
    assert all(any(f["name"] == "area" for f in r["factors"]) for r in data["results"])
    assert search_mod.NEARBY_MAX_KM == 6.0
