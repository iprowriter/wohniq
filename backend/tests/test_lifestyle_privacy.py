"""Privacy by design (ADR-0012): answers are not stored and not logged.

Each test sends distinctive values and checks they appear in no log record at any
level — message, arguments, or exception text — and that the stateless endpoints never
ask for a database session.
"""

import logging
import re

import httpx
import pytest
from fastapi.testclient import TestClient

import app.routers.search as search_mod
import enrich.commute as commute_mod
from app.main import app
from app.repository import get_repository
from core.llm import generate_structured
from search.criteria import SearchCriteria
from search.explanation import Explanation
from search.retrieval import RetrievalResult
from tests.fake_repository import FakeRepository

client = TestClient(app)
API = "/api/v1/lifestyle"

# Values nobody would produce by accident.
SECRET_ANSWERS = {
    "budget_eur": 4321,
    "size_m2": 187,
    "rooms": 5.5,
    "max_commute_min": 73,
    "destination": "hu_adlershof",
    "frequency": "daily",
    "evenings": "out_often",
    "weekends": ["nature", "culture"],
    "safety": "lot",
}
SECRET_EXCLUDED = ["095019"]
SECRETS = ["4321", "187", "5.5", "73", "hu_adlershof", "095019", "out_often", "nature"]


def _log_text(caplog) -> str:
    parts = []
    for rec in caplog.records:
        parts.append(rec.getMessage())
        parts.append(repr(rec.args))
        if rec.exc_text:
            parts.append(rec.exc_text)
    return "\n".join(parts)


def _leaks(text: str, secrets) -> list[str]:
    """Secrets found as whole tokens (so "73" doesn't match a latency of 15.735 ms)."""
    return [s for s in secrets if re.search(rf"(?<![\w.]){re.escape(s)}(?![\w.])", text)]


@pytest.fixture
def all_logs(caplog):
    caplog.set_level(logging.DEBUG)  # every logger, every level
    return caplog


def test_lifestyle_answers_never_reach_the_logs(all_logs):
    profile = client.post(f"{API}/profile", json={"answers": SECRET_ANSWERS})
    match = client.post(
        f"{API}/match", json={"answers": SECRET_ANSWERS, "excluded": SECRET_EXCLUDED}
    )
    bad = client.post(f"{API}/match", json={"answers": {**SECRET_ANSWERS, "budget_eur": 43210}})
    assert profile.status_code == 200 and match.status_code == 200 and bad.status_code == 422
    text = _log_text(all_logs)
    assert "lifestyle match results=" in text  # we do log — counts only
    leaked = _leaks(text, SECRETS + ["43210"])
    offending = [line for line in text.splitlines() if _leaks(line, leaked)]
    assert not leaked, f"answer values found in logs: {leaked}: {offending[:5]}"


def test_listing_handoff_does_not_log_its_inputs(all_logs):
    r = client.post(
        f"{API}/listings", json={"region_key": "043006", "budget_eur": 4321, "min_rooms": 5.5}
    )
    assert r.status_code == 200
    assert not _leaks(_log_text(all_logs), ["4321", "5.5"])


def test_stateless_endpoints_never_open_the_repository():
    """/profile and /match compute from the shipped data only: no DB, nothing stored."""
    calls = []

    def spy():
        calls.append(1)
        raise AssertionError("repository must not be used")

    app.dependency_overrides[get_repository] = spy
    try:
        assert client.post(f"{API}/profile", json={"answers": SECRET_ANSWERS}).status_code == 200
        assert client.post(f"{API}/match", json={"answers": SECRET_ANSWERS}).status_code == 200
        assert client.get(f"{API}/catalog").status_code == 200
    finally:
        app.dependency_overrides.clear()
    assert calls == []


def test_responses_are_not_cacheable():
    for path, body in [
        ("profile", {"answers": SECRET_ANSWERS}),
        ("match", {"answers": SECRET_ANSWERS}),
        ("listings", {"region_key": "043006"}),
    ]:
        assert client.post(f"{API}/{path}", json=body).headers["cache-control"] == "no-store"


def test_answers_only_travel_in_post_bodies():
    """No lifestyle route accepts answers via GET/query string (access logs record URLs)."""
    routes = [r for r in app.routes if getattr(r, "path", "").startswith("/api/v1/lifestyle")]
    for route in routes:
        if route.path.endswith(("/profile", "/match", "/listings")):
            assert route.methods == {"POST"}
        else:
            assert route.methods == {"GET"}
            assert not route.dependant.query_params  # nothing to put in a URL


# --- /search and shared helpers are redacted too ------------------------------------------


def test_search_logs_neither_query_nor_parsed_values(all_logs, monkeypatch):
    monkeypatch.setattr(
        search_mod,
        "parse_query",
        lambda text, **kw: SearchCriteria(max_warm_rent=1777, work_location="Geheimweg 9"),
    )
    monkeypatch.setattr(
        search_mod,
        "explain",
        lambda result, **kw: Explanation(summary="ok", reasons=[], caveats=[]),
    )
    from tests.test_search_api import _listing

    flat = _listing("Flat", "Mitte", 1100)
    repo = FakeRepository(retrieval=[RetrievalResult(flat, 0.2)])
    app.dependency_overrides[get_repository] = lambda: repo
    try:
        r = client.post(
            "/api/v1/search", json={"query": "SECRET-QUERY near Geheimweg 9 under 1777"}
        )
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    text = _log_text(all_logs)
    assert "search results=1" in text and "work_location" in text  # field names only
    assert not _leaks(text, ["SECRET-QUERY", "Geheimweg", "1777"])


def test_commute_failures_do_not_log_the_destination(all_logs, monkeypatch):
    def boom(*a, **kw):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(commute_mod, "resolve_location", boom)

    class NoCache:
        def get(self, *a):
            return None

    commute_mod.get_commute(NoCache(), 52.52, 13.40, "Geheimweg 9")
    text = _log_text(all_logs)
    assert "commute lookup failed" in text and "Geheimweg" not in text


def test_llm_validation_failures_do_not_log_model_output(all_logs):
    from core.llm import RawResponse

    def transport(system, user, schema, temperature):
        return RawResponse(text='{"max_warm_rent": "SECRET-ECHO Geheimweg 9"}')

    result = generate_structured(
        prompt_id="test",
        system="s",
        user="u",
        schema=SearchCriteria,
        fallback=SearchCriteria,
        transport=transport,
    )
    assert result.used_fallback
    text = _log_text(all_logs)
    assert "invalid" in text and "max_warm_rent" in text  # where, not what
    assert "SECRET-ECHO" not in text and "Geheimweg" not in text
