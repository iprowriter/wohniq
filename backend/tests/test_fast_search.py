"""Fast search (ADR-0022): time limits, service errors, batched explanations and the
parallel page enrichment. No network, no database, no Gemini."""

import json
import threading
import time
from contextlib import contextmanager

import pytest

import enrich.page as page
from core.llm import LLMError, RawResponse, generate_structured
from enrich.commute_parse import CommuteResult
from enrich.neighborhood_parse import NeighborhoodResult
from search import explanation as ex
from search.criteria import SearchCriteria
from search.parser import parse_query
from search.ranking import FactorScore, RankingResult

# --- core.llm: time limit and service errors -------------------------------------------


def _slow(seconds, text='{"max_warm_rent": 900}'):
    def transport(system, user, schema, temperature):
        time.sleep(seconds)
        return RawResponse(text)

    return transport


def test_slow_model_hands_over_to_the_fallback_on_time():
    start = time.perf_counter()
    res = generate_structured(
        prompt_id="t",
        system="s",
        user="u",
        schema=SearchCriteria,
        fallback=lambda: SearchCriteria(max_warm_rent=1),
        transport=_slow(2.0),
        timeout_s=0.2,
    )
    assert time.perf_counter() - start < 1.0
    assert res.used_fallback and res.data.max_warm_rent == 1


def test_fast_model_within_the_limit_is_used():
    res = generate_structured(
        prompt_id="t",
        system="s",
        user="u",
        schema=SearchCriteria,
        fallback=lambda: SearchCriteria(),
        transport=_slow(0.01),
        timeout_s=2,
    )
    assert not res.used_fallback and res.data.max_warm_rent == 900


def test_service_error_uses_the_fallback_or_raises_llmerror_without_one():
    def broken(*a):
        raise RuntimeError("404 model no longer available")

    res = generate_structured(
        prompt_id="t",
        system="s",
        user="u",
        schema=SearchCriteria,
        fallback=lambda: SearchCriteria(min_rooms=2),
        transport=broken,
    )
    assert res.used_fallback and res.data.min_rooms == 2
    with pytest.raises(LLMError):
        generate_structured(
            prompt_id="t", system="s", user="u", schema=SearchCriteria, transport=broken
        )


def test_parser_answers_with_keywords_when_the_model_is_slow():
    criteria = parse_query("2 rooms in Mitte under 1200", transport=_slow(2.0), timeout_s=0.2)
    assert criteria.max_warm_rent == 1200 and "Mitte" in criteria.areas


# --- batched explanations --------------------------------------------------------------


def _result(i):
    return RankingResult(
        total=0.8,
        factors=[
            FactorScore(
                "budget", 0.9, 2, f"€{1000 + i} warm, under your €1.500 budget", "under budget"
            )
        ],
    )


def test_batch_prompt_keeps_every_explain_rule_and_adds_the_batch_ones():
    s = ex.EXPLAIN_BATCH_SYSTEM
    assert '{"items": [...]}' in s and "Listing #n" in s and "never carry a value" in s
    assert "why each of several listings fits" in s
    for rule in ("Do NOT invent facts", "caveats", "Never write only"):
        assert rule in s


def test_explain_many_sends_ten_per_call_in_parallel_and_keeps_order():
    calls, lock = [], threading.Lock()

    def transport(system, user, schema, temperature):
        n = user.count("Listing #")
        with lock:
            calls.append(n)
        time.sleep(0.3)
        items = [
            {
                "ref": r,
                "summary": f"Item {r}: €{r} under your budget.",
                "reasons": [],
                "caveats": [],
            }
            for r in range(1, n + 1)
        ]
        return RawResponse(json.dumps({"items": items}))

    start = time.perf_counter()
    out = ex.explain_many([(_result(i), None) for i in range(25)], transport=transport)
    assert sorted(calls) == [5, 10, 10]
    assert time.perf_counter() - start < 0.8  # the three calls overlapped
    assert all(ai for _, ai in out) and len(out) == 25
    assert out[10][0].summary.startswith("Item 1:")  # first of the second batch


def test_explain_many_never_raises_and_falls_back_per_item():
    def broken(*a):
        raise RuntimeError("quota")

    out = ex.explain_many([(_result(i), None) for i in range(3)], transport=broken)
    assert [ai for _, ai in out] == [False, False, False]
    assert all(e.summary for e, _ in out)


# --- parallel page enrichment ------------------------------------------------------------


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Session:
    """Answers the two cache queries: neighbourhood rows first, then commute rows."""

    def __init__(self, n_rows=(), c_rows=()):
        self._answers = [list(n_rows), list(c_rows)]

    def scalars(self, _stmt):
        return self._answers.pop(0)


@contextmanager
def _own_session():
    yield object()


NEIGH = NeighborhoodResult(
    counts={"cafes": 3}, pois=[], summary="live", available_amenities={"cafes"}
)
BUNDLED = NeighborhoodResult(counts={}, pois=[], summary="bundled", available_amenities=set())


def test_cached_answers_need_no_lookup(monkeypatch):
    def no_lookup(*a):
        raise AssertionError("cached point looked up")

    monkeypatch.setattr(page, "fetch_neighborhood", no_lookup)
    monkeypatch.setattr(page, "fetch_live_commute", no_lookup)
    n_row = _Row(location_key="52.5,13.4", poi_counts={"parks": 2}, pois=[], summary="cached")
    c_row = _Row(origin_key="52.5,13.4", minutes=17, changes=1, walk_minutes=5)
    out = page.enrich_page(
        _Session([n_row], [c_row]),
        _own_session,
        [(52.5, 13.4)],
        "Alexanderplatz",
        timeout_s=1,
        offline_neighborhood=lambda a, b: None,
    )
    ((neigh, commute),) = out
    assert neigh.summary == "cached" and commute.minutes == 17 and not commute.estimated


def test_slow_lookups_get_offline_answers_in_time_and_fast_ones_count(monkeypatch):
    def neighbourhood(lat, lng):
        time.sleep(0.05 if lat < 52.51 else 2.0)
        return NEIGH

    def commute(lat, lng, work):
        time.sleep(2.0)
        return CommuteResult(10, 0, 2), None

    stored = []
    monkeypatch.setattr(page, "fetch_neighborhood", neighbourhood)
    monkeypatch.setattr(page, "fetch_live_commute", commute)
    monkeypatch.setattr(page, "store_neighborhood", lambda s, lat, lng, r: stored.append(lat))
    monkeypatch.setattr(page, "store_commute", lambda *a: None)
    start = time.perf_counter()
    out = page.enrich_page(
        _Session(),
        _own_session,
        [(52.50, 13.40), (52.55, 13.45)],
        "Alexanderplatz",
        timeout_s=0.4,
        offline_neighborhood=lambda a, b: BUNDLED,
    )
    assert time.perf_counter() - start < 1.0
    assert out[0][0].summary == "live"  # answered in time
    assert out[1][0].summary == "bundled"  # too slow: bundled data
    for _, c in out:  # live trips too slow: the offline estimate, labelled as one
        assert c is not None and c.estimated
    assert stored == [52.50]  # the answer that came back was stored for next time


def test_no_work_location_means_no_commute_lookups(monkeypatch):
    monkeypatch.setattr(page, "fetch_neighborhood", lambda a, b: NEIGH)
    monkeypatch.setattr(page, "store_neighborhood", lambda *a: None)
    monkeypatch.setattr(page, "fetch_live_commute", lambda *a: pytest.fail("commute looked up"))
    out = page.enrich_page(
        _Session(),
        _own_session,
        [(52.5, 13.4)],
        None,
        timeout_s=1,
        offline_neighborhood=lambda a, b: None,
    )
    assert out == [(NEIGH, None)]


def test_the_same_point_is_looked_up_once_at_a_time(monkeypatch):
    calls = []

    def neighbourhood(lat, lng):
        calls.append((lat, lng))
        time.sleep(0.2)
        return NEIGH

    monkeypatch.setattr(page, "fetch_neighborhood", neighbourhood)
    monkeypatch.setattr(page, "store_neighborhood", lambda *a: None)
    out = page.enrich_page(
        _Session(),
        _own_session,
        [(52.5, 13.4), (52.5, 13.4)],
        None,
        timeout_s=1,
        offline_neighborhood=lambda a, b: None,
    )
    assert len(calls) == 1 and [n for n, _ in out] == [NEIGH, NEIGH]
