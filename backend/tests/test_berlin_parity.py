"""Parity: the Supabase/PostGIS and the in-memory Berlin data give the same answers (ADR-0016).

Slow and opt-in (`make test-all`): needs `make berlin-data`, a DATABASE_URL, and
`make berlin-load`. Points: a fixed sample of real addresses spread across Berlin, plus
park centres and a few non-address points.
"""

from __future__ import annotations

import pytest

from berlin import files

pytestmark = pytest.mark.slow

POINT_TOL_M = 0.5  # same sphere, same coordinates: only float noise
PARK_TOL_M = 1.0  # planar segments vs great-circle edges


@pytest.fixture(scope="module")
def both():
    if not files.is_built():
        pytest.skip("run `make berlin-data` first")
    from core.config import settings

    if not settings.database_url.strip():
        pytest.skip("no DATABASE_URL")
    from sqlalchemy import text

    from berlin.local import LocalBerlinData
    from berlin.postgres import PostgresBerlinData
    from core.db import get_engine

    engine = get_engine()
    with engine.connect() as c:
        try:
            n = c.execute(text("SELECT count(*) FROM berlin_address")).scalar()
        except Exception:  # noqa: BLE001 - table missing = not migrated
            pytest.skip("berlin tables missing (make migrate)")
    if not n:
        pytest.skip("berlin tables empty (make berlin-load)")
    return LocalBerlinData(), PostgresBerlinData(engine)


@pytest.fixture(scope="module")
def points(both):
    local, _ = both
    n = len(local._addr_rows)
    pts = [(float(local.addr_lat[i]), float(local.addr_lng[i])) for i in range(0, n, n // 25)]
    pts += [(p["lat"], p["lng"]) for p in local._parks[::120]]
    pts += [(52.5163, 13.3777), (52.4730, 13.4030), (52.4400, 13.2200)]  # Tor, Feld, Grunewald
    return pts


def test_addresses(both):
    local, pg = both
    for q in ("choriner str 41", "sebastianstr", "karl marx allee 1", "muellerstr 4"):
        assert local.search_addresses(q, 15) == pg.search_addresses(q, 15), q
    for address_id in (1, 1234, 200_000, 400_505):
        assert local.address(address_id) == pg.address(address_id)


def test_nearest_address_and_class_share(both, points):
    local, pg = both
    for lat, lng in points:
        assert local.nearest_address(lat, lng) == pg.nearest_address(lat, lng)
        a, b = local.location_class_share(lat, lng, 300), pg.location_class_share(lat, lng, 300)
        assert a.keys() == b.keys()
        for k in a:
            assert a[k] == pytest.approx(b[k], abs=0.02)


def test_area_at(both, points):
    local, pg = both
    for lat, lng in points:
        assert local.area_at(lat, lng) == pg.area_at(lat, lng), (lat, lng)


def test_stops(both, points):
    local, pg = both
    rail = frozenset({"sbahn", "ubahn"})
    for lat, lng in points:
        for modes in (None, rail):
            a, b = local.nearest_stops(lat, lng, 6, modes), pg.nearest_stops(lat, lng, 6, modes)
            assert [s.id for s in a] == [s.id for s in b]
            for s, t in zip(a, b, strict=True):
                assert s.distance_m == pytest.approx(t.distance_m, abs=POINT_TOL_M)


@pytest.mark.parametrize(
    "layer,radius", [("schools", 1000), ("kitas", 500), ("playgrounds", 500), ("accidents", 300)]
)
def test_point_layers(both, points, layer, radius):
    local, pg = both
    for lat, lng in points:
        a, b = local.within(layer, lat, lng, radius), pg.within(layer, lat, lng, radius)
        assert len(a) == len(b), (layer, lat, lng)
        for x, y in zip(a, b, strict=True):
            assert x["distance_m"] == pytest.approx(y["distance_m"], abs=POINT_TOL_M)
            assert {k: v for k, v in x.items() if k != "distance_m"} == {
                k: v for k, v in y.items() if k != "distance_m"
            }


def test_parks_and_air(both, points):
    local, pg = both
    for lat, lng in points:
        a, b = local.nearest_park(lat, lng), pg.nearest_park(lat, lng)
        assert a.distance_m == pytest.approx(b.distance_m, abs=PARK_TOL_M), (lat, lng)
        if abs(a.distance_m - b.distance_m) < 1e-6:
            assert a.name == b.name
        assert local.nearest_air_station(lat, lng).code == pg.nearest_air_station(lat, lng).code


def test_tables_and_documents(both):
    local, pg = both
    assert local.rent_rows() == pg.rent_rows()
    assert local.rent_periods() == pg.rent_periods()
    assert local.checklist() == pg.checklist()
    assert local.crime_rates() == pg.crime_rates()
    assert local.berlin_crime_rate() == pg.berlin_crime_rate()
    assert local.area_stats() == pg.area_stats()


def test_map_layers(both):
    local, pg = both
    for box in ((52.52, 13.39, 52.54, 13.42), (52.45, 13.20, 52.50, 13.30)):
        assert local.stops_in_bbox(*box) == pg.stops_in_bbox(*box)
        a, b = local.parks_in_bbox(*box), pg.parks_in_bbox(*box)
        assert [p["name"] for p in a] == [p["name"] for p in b]
        assert [p["area_m2"] for p in a] == [p["area_m2"] for p in b]
