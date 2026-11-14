"""Berlin Neighbourhoods — spatial measurements (synthetic geometry, offline)."""

import struct

import pytest

from data.lifestyle import geo
from data.lifestyle.access import _PolygonLookup
from data.neighborhoods import measure
from data.neighborhoods.parse import Accident
from tests.test_lifestyle_access import _gp, _make_gpkg, _square, _wkb_point, _wkb_polygon


def _wkb_line(points, order="<"):
    out = bytes([1 if order == "<" else 0]) + struct.pack(order + "II", 2, len(points))
    for lng, lat in points:
        out += struct.pack(order + "dd", lng, lat)
    return out


def _xy(lng, lat):
    return geo.to_xy(lng, lat)


def _indexes(pois=(), hospitals=(), parks=(), meters=(), parking=()):
    facilities = {fid: geo.GridIndex(f.radius_m) for fid, f in measure.FACILITIES.items()}
    for fid, lng, lat in pois:
        facilities[fid].add(*_xy(lng, lat), fid)
    h = geo.GridIndex(3000)
    for lng, lat in hospitals:
        h.add(*_xy(lng, lat))
    p = geo.GridIndex(500)
    for lng, lat in parks:
        p.add(*_xy(lng, lat))
    m = geo.GridIndex(200)
    for lng, lat in meters:
        m.add(*_xy(lng, lat))
    w = measure.WeightedGrid(300)
    for lng, lat, area in parking:
        w.add(*_xy(lng, lat), area)
    return facilities, h, p, m, w


def test_measure_homes_means_over_home_points():
    # Two homes ~700 m apart (0.01° lng); one pharmacy next to the first only.
    homes = [_xy(13.40, 52.50), _xy(13.41, 52.50)]
    idx = _indexes(
        pois=[("pharmacies", 13.4001, 52.5001), ("schools", 13.405, 52.50)],
        hospitals=[(13.40, 52.52)],  # ~2.2 km north of the first home
        meters=[(13.4101, 52.5001)],  # next to the second home
        parking=[(13.40, 52.501, 500.0), (13.45, 52.50, 9999.0)],  # second is > 300 m away
    )
    r = measure.measure_homes(homes, *idx)
    assert r.homes == 2
    assert r.counts["pharmacies"] == 0.5  # 1 of 2 homes has one within 500 m
    assert r.counts["schools"] == 1.0  # 340 m from both: within 1 km
    assert 2200 < r.hospital_m < 2400
    assert r.park_m == measure.PARK_CAP_M  # no park at all → capped
    assert r.paid_parking_share == 50.0
    assert r.parking_area_m2 == 250.0  # 500 m² near the first home only


def test_paid_parking_radius_is_inclusive_and_tight():
    home = _xy(13.40, 52.50)
    near = geo.to_lnglat(home[0] + 149, home[1])
    far = geo.to_lnglat(home[0] + 160, home[1])
    assert measure.measure_homes([home], *_indexes(meters=[near])).paid_parking_share == 100
    assert measure.measure_homes([home], *_indexes(meters=[far])).paid_parking_share == 0


def test_facility_classes_are_disjoint():
    seen: set[str] = set()
    for f in measure.FACILITIES.values():
        assert not (f.fclasses & seen)
        seen |= f.fclasses
    assert "hospital" not in seen  # hospitals are a distance, not a count


def _lookup():
    return _PolygonLookup(
        {
            "011001": [[_square(13.39, 52.49, 0.02)]],
            "011002": [[_square(13.41, 52.49, 0.02)]],
        }
    )


def test_assign_accidents_counts_severity_and_vulnerable_users():
    acc = [
        Accident(13.395, 52.495, 3, bike=True, pedestrian=False),
        Accident(13.395, 52.496, 2, bike=False, pedestrian=False),
        Accident(13.415, 52.495, 1, bike=False, pedestrian=True),
        Accident(10.0, 53.9, 3, bike=False, pedestrian=False),  # outside every region
    ]
    out = measure.assign_accidents(acc, _lookup())
    a, b = out["011001"], out["011002"]
    assert (a.accidents, a.severe, a.vulnerable) == (2, 1, 1)
    assert (b.accidents, b.severe, b.vulnerable) == (1, 1, 1)


def test_street_km_splits_a_street_at_the_region_border():
    # 0.02° of longitude ≈ 1.354 km at Berlin's latitude, half in each region.
    line = [(13.40, 52.50), (13.41, 52.50), (13.42, 52.50)]
    km = measure.street_km_by_region([line], _lookup())
    assert km["011001"] == pytest.approx(0.677, abs=0.01)
    assert km["011002"] == pytest.approx(0.677, abs=0.01)


def test_read_lines_decodes_linestrings_and_filters_classes(tmp_path):
    path = tmp_path / "roads.gpkg"
    _make_gpkg(
        path,
        {
            "gis_osm_roads_free": [
                ("residential", _gp(_wkb_line([(13.4, 52.5), (13.41, 52.5)]))),
                ("footway", _gp(_wkb_line([(13.4, 52.5), (13.5, 52.5)]))),
                ("primary", _gp(_wkb_line([(13.4, 52.5), (13.4, 52.51)], ">"))),
            ]
        },
    )
    lines = list(measure.read_lines(path, "gis_osm_roads_free", measure.STREET_CLASSES))
    assert lines == [[(13.4, 52.5), (13.41, 52.5)], [(13.4, 52.5), (13.4, 52.51)]]


def test_measure_access_end_to_end(tmp_path):
    gpkg = tmp_path / "mini.gpkg"
    home = _square(13.400, 52.500, 0.003)
    _make_gpkg(
        gpkg,
        {
            "gis_osm_landuse_a_free": [
                ("residential", _gp(_wkb_polygon([home]))),
                ("park", _gp(_wkb_polygon([_square(13.404, 52.500, 0.003)]))),  # ~4 ha
                ("park", _gp(_wkb_polygon([_square(13.4005, 52.5005, 0.0002)]))),  # tiny
            ],
            "gis_osm_pois_free": [
                ("pharmacy", _gp(_wkb_point(13.4015, 52.5015))),
                ("vending_parking", _gp(_wkb_point(13.4015, 52.5015))),
            ],
            "gis_osm_pois_a_free": [("hospital", _gp(_wkb_polygon([_square(13.42, 52.5, 0.002)])))],
            "gis_osm_transport_free": [("bus_stop", _gp(_wkb_point(13.401, 52.501)))],
            "gis_osm_transport_a_free": [],
            "gis_osm_traffic_a_free": [
                ("parking", _gp(_wkb_polygon([_square(13.4012, 52.5012, 0.0003)])))
            ],
        },
    )
    regions = {
        "011001": [[_square(13.39, 52.49, 0.03)]],
        "011002": [[_square(13.60, 52.60, 0.01)]],  # no residential land → centre point
    }
    out = measure.measure_access(
        gpkg, regions, {"011001": (52.5, 13.4), "011002": (52.605, 13.605)}
    )
    a = out["011001"]
    assert a.homes > 0
    assert a.counts["pharmacies"] == 1 and a.counts["stops"] == 1
    assert 1000 < a.hospital_m < 1600
    assert a.park_m < 300  # the 4 ha park next door, not the tiny one
    assert a.paid_parking_share > 50 and a.parking_area_m2 > 0
    assert out["011002"].homes == 0


# --- Land values at homes --------------------------------------------------------------------


def test_class_percentile_counts_ties_half():
    assert measure.class_percentile([100.0, 200.0, 300.0, 400.0], 400.0) == 87.5
    assert measure.class_percentile([100.0, 200.0, 300.0, 400.0], 100.0) == 12.5
    assert measure.class_percentile([5.0, 5.0], 5.0) == 50.0


def test_land_values_compare_houses_with_houses_and_flats_with_flats():
    from data.neighborhoods.parse import LandZone

    def zone(zid, lng, value, density):
        return LandZone(zid, [[_square(lng, 52.50, 0.01)]], value, None, "W", density)

    zones = [
        zone("villa", 13.40, 2000.0, "houses"),  # priciest houses zone
        zone("house", 13.42, 400.0, "houses"),
        zone("flats-cheap", 13.44, 1000.0, "flats"),
        zone("flats-prime", 13.46, 6000.0, "flats"),
    ]
    samples = {
        "011001": [_xy(13.405, 52.505)],  # in the villa zone
        "011002": [_xy(13.445, 52.505), _xy(13.50, 52.505)],  # cheap flats + outside any zone
        "011003": [_xy(13.60, 52.60)],  # no zone at all
    }
    out = measure.land_values(samples, zones)
    assert out["011001"].index == 75.0  # top of 2 house zones, although €2,000 < €6,000
    assert out["011001"].median_eur == 2000.0 and out["011001"].houses_share == 100.0
    assert out["011002"].index == 25.0 and (out["011002"].homes, out["011002"].homes_total) == (
        1,
        2,
    )
    assert "011003" not in out
