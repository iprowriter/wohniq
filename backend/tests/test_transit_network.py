"""Route-based commute estimate over the peak network (enrich/transit_network.py)."""

import pytest

import enrich.commute as commute
from data.vbb_network import extract_network, write_network
from enrich.commute_estimate import estimate_commute
from enrich.transit_network import ALIGHT_MIN, load_network, walk_minutes
from tests.gtfs_fixture import STATIONS, build_gtfs


def _at(sid):
    _name, lat, lng = STATIONS[sid]
    return lat, lng


@pytest.fixture(scope="module")
def network(tmp_path_factory):
    d = tmp_path_factory.mktemp("net")
    write_network(extract_network(build_gtfs(d / "feed.zip")), d)
    return load_network(d)


def test_direct_ride_prefers_faster_express(network):
    # A→C: express R1 (wait 10 + ride 6) beats U1 (wait 2.4 + 2 × 10), plus alighting.
    route = network.route(*_at("A"), *_at("C"))
    assert route.minutes == pytest.approx(10 + 6 + ALIGHT_MIN)
    assert route.changes == 0
    assert route.legs[1].startswith("R1 ")


def test_transfer_counts_one_change(network):
    # D→C: S1 to B, change, U1 to C.
    route = network.route(*_at("D"), *_at("C"))
    assert route.changes == 1
    assert route.minutes == pytest.approx(5 + 8 + ALIGHT_MIN + 2.5 + 10 + ALIGHT_MIN)
    assert [leg.split()[0] for leg in route.legs if not leg.startswith("walk")] == ["S1", "U1"]


def test_walking_link_between_nearby_stations(network):
    # A→E: U1 to B, walk ~200 m to bus stop F, bus X to E. The rare U1 diversion and the
    # night/weekend lines (all A→E in ≤ 5 min) must not be used.
    route = network.route(*_at("A"), *_at("E"))
    names = [leg.split()[0] for leg in route.legs if not leg.startswith("walk")]
    assert names == ["U1", "X"]
    assert route.changes == 1
    assert route.minutes > 30


def test_short_trip_is_walked(network):
    lat, lng = _at("B")
    route = network.route(lat, lng, lat + 0.003, lng)  # ~330 m
    assert not route.uses_transit
    assert route.minutes == pytest.approx(walk_minutes(0.3336), abs=0.2)


def test_access_walk_is_counted(network):
    lat, lng = _at("A")
    near = network.route(lat, lng, *_at("C"))
    farther = network.route(lat + 0.005, lng, *_at("C"))  # ~550 m from A
    assert farther.minutes > near.minutes
    assert farther.walk_minutes > near.walk_minutes


def test_estimate_between_uses_network(monkeypatch, network):
    monkeypatch.setattr(commute, "get_network", lambda: network)
    result = commute.estimate_between(*_at("D"), *_at("C"))
    assert result.source == "network" and result.estimated
    assert result.changes == 1
    assert isinstance(result.minutes, int)


def test_estimate_between_falls_back_without_network(monkeypatch):
    monkeypatch.setattr(commute, "get_network", lambda: None)
    result = commute.estimate_between(*_at("D"), *_at("C"))
    assert result == estimate_commute(*_at("D"), *_at("C"))
    assert result.source == "distance"


def test_estimate_between_falls_back_when_no_station_nearby(monkeypatch, network):
    # Far from every station: walking all the way would be absurd; use straight-line.
    monkeypatch.setattr(commute, "get_network", lambda: network)
    result = commute.estimate_between(52.62, 13.10, *_at("C"))
    assert result.source == "distance"
