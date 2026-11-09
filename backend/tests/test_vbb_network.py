"""Building the weekday-peak network from GTFS (data/vbb_network.py), on a synthetic feed."""

from datetime import date

import pytest

from data.vbb_network import extract_network, pick_reference_date, write_network
from enrich.transit_network import load_network
from tests.gtfs_fixture import build_gtfs


@pytest.fixture(scope="module")
def gtfs(tmp_path_factory):
    return build_gtfs(tmp_path_factory.mktemp("gtfs") / "feed.zip")


@pytest.fixture(scope="module")
def net(gtfs):
    return extract_network(gtfs)


def _ride(net, line, a, b):
    return next(
        (r for r in net.rides if (r["line"], r["from_station"], r["to_station"]) == (line, a, b)),
        None,
    )


def _wait(net, line, station):
    return next(
        b["wait_minutes"] for b in net.boardings if (b["line"], b["station"]) == (line, station)
    )


def test_picks_busiest_midweek_day(net):
    # Tue 2026-01-06 lost the express service (calendar_dates), so Wednesday wins.
    assert net.meta["reference_date"] == "2026-01-07"
    assert net.meta["weekday"] == "Wednesday"
    assert net.meta["peak_window"] == "07:00-09:00"


def test_platforms_fold_into_their_station(net):
    assert set(net.stations) == {"A", "B", "C", "D", "F", "E"}
    assert _ride(net, "U1|0", "A", "B") is not None  # stop_times used "A:1" / "B:1"


def test_ride_time_is_median_scheduled_time(net):
    assert _ride(net, "U1|0", "A", "B")["minutes"] == 10.0
    assert _ride(net, "S1|0", "D", "B")["minutes"] == 8.0


def test_wait_is_half_the_peak_gap(net):
    assert _wait(net, "S1|0", "D") == 5.0  # every 10 min
    assert _wait(net, "U1|1", "C") == 2.5  # every 5 min
    assert _wait(net, "R1|0", "A") == 10.0  # every 20 min


@pytest.mark.parametrize(
    ("line", "why"),
    [("U1|0", "one-off diversion"), ("N1|0", "night line"), ("W1|0", "weekend-only")],
)
def test_shortcuts_to_e_are_excluded(net, line, why):
    assert _ride(net, line, "A", "E") is None, why


def test_calendar_exception_removes_service(gtfs):
    tuesday = extract_network(gtfs, reference_date=date(2026, 1, 6))
    assert _ride(tuesday, "R1|0", "A", "C") is None
    assert _ride(tuesday, "U1|0", "A", "B") is not None


def test_reference_date_requires_weekday_service():
    with pytest.raises(ValueError):
        pick_reference_date([], {})


def test_written_network_loads_back(net, tmp_path):
    write_network(net, tmp_path)
    loaded = load_network(tmp_path)
    assert set(loaded.stations) == set(net.stations)
    assert ("B", 10.0) in loaded.rides[("U1|0", "A")]
    assert (tmp_path / "network_meta.json").is_file()


def test_missing_files_load_as_none(tmp_path):
    assert load_network(tmp_path) is None
