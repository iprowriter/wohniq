"""Commute eval: pure metrics, and the runner end to end with the live API stubbed."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import evals.commute_eval as ev
from data.vbb_network import extract_network, write_network
from enrich.transit_network import load_network
from evals.commute_metrics import changes_accuracy, error_stats, order_agreement, verdict
from tests.gtfs_fixture import build_gtfs


def test_error_stats():
    s = error_stats([30, 20, 50], [25, 20, 40])  # errors +5, 0, +10
    assert s == {
        "n": 3,
        "mae": 5.0,
        "median_abs_error": 5,
        "bias": 5.0,
        "within_5_min": 0.667,
        "within_10_min": 1.0,
    }
    assert error_stats([], []) == {"n": 0}
    with pytest.raises(ValueError):
        error_stats([1], [])


def test_changes_accuracy():
    assert changes_accuracy([0, 1, 3], [0, 2, 1]) == {"n": 3, "exact": 0.333, "within_1": 0.667}


def test_order_agreement_is_what_ranking_needs():
    live = [20, 30, 40]
    assert order_agreement([25, 30, 45], live) == 1.0  # same order
    assert order_agreement([40, 30, 20], live) == 0.0  # reversed
    assert order_agreement([30, 30, 30], live) is None  # all ties: can't tell apart


def test_verdict():
    assert verdict({"distance": {"n": 5, "mae": 9.0}, "network": {"n": 5, "mae": 4.5}}).startswith(
        "network is more accurate"
    )
    assert verdict({"distance": {"n": 5, "mae": 9.0}}) == "not enough data to compare"


def test_next_weekday_peak_is_tue_to_thu_8am_berlin():
    friday = datetime(2026, 11, 6, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert ev.next_weekday_peak(friday) == "2026-11-10T08:00:00+01:00"  # Tuesday, CET


def test_runner_end_to_end_with_stubbed_api(monkeypatch, tmp_path):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(ev, "LIVE_CACHE", tmp_path / "commute_live.json")
    monkeypatch.setattr(ev, "API_PAUSE_S", 0)
    calls = {"resolve": 0, "journey": 0}

    def resolve(name):
        calls["resolve"] += 1
        return {"id": name, "name": name, "location": {"latitude": 52.52, "longitude": 13.41}}

    def journey(lat, lng, stop_id, *, departure):
        calls["journey"] += 1
        assert departure.endswith(("+01:00", "+02:00")) and "T08:00" in departure
        return {"stub": True}

    monkeypatch.setattr(ev.live, "resolve_location", resolve)
    monkeypatch.setattr(ev.live, "fetch_first_journey", journey)
    monkeypatch.setattr(
        ev, "parse_journey", lambda j: ev.live.CommuteResult(minutes=25, changes=1, walk_minutes=6)
    )

    listings, dests = ev.sample_listings(3), ["Alexanderplatz", "Südkreuz"]
    cache = ev.collect_live(listings, dests, offline=False, departure=ev.next_weekday_peak())
    assert calls == {"resolve": 2, "journey": 6}

    # Re-running only queries what's missing (nothing), and --offline never calls the API.
    ev.collect_live(listings, dests, offline=False, departure=ev.next_weekday_peak())
    ev.collect_live(listings, dests, offline=True, departure=ev.next_weekday_peak())
    assert calls == {"resolve": 2, "journey": 6}

    d = tmp_path / "net"
    d.mkdir()
    write_network(extract_network(build_gtfs(d / "feed.zip")), d)
    report = ev.score(listings, dests, cache, load_network(d))
    assert report["pairs"] == 6
    assert set(report["methods"]) == {"distance", "network"}
    assert report["methods"]["distance"]["n"] == 6
    assert "network_changes" in report
    assert "Verdict" in ev._markdown(report, "2026-11-10T08:00:00+01:00")
