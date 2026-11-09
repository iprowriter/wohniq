"""Lifestyle Match: GeoPackage decoding, geometry helpers and walking-distance access."""

import sqlite3
import struct

import pytest

from data.lifestyle import access, geo, osm

# --- GeoPackage blob builders ---------------------------------------------------------


def _gp(wkb: bytes, envelope: tuple[float, ...] | None = None) -> bytes:
    """GeoPackage binary header (+ optional xy envelope) around a WKB body."""
    flags = 0b1 | ((1 if envelope else 0) << 1)  # little-endian header, envelope type 1
    head = b"GP" + bytes([0, flags]) + struct.pack("<i", 100000)
    if envelope:
        head += struct.pack("<4d", *envelope)
    return head + wkb


def _wkb_point(lng, lat, order="<"):
    return bytes([1 if order == "<" else 0]) + struct.pack(order + "Idd", 1, lng, lat)


def _wkb_polygon(rings, order="<"):
    out = bytes([1 if order == "<" else 0]) + struct.pack(order + "II", 3, len(rings))
    for ring in rings:
        out += struct.pack(order + "I", len(ring))
        for lng, lat in ring:
            out += struct.pack(order + "dd", lng, lat)
    return out


def _wkb_multipolygon(polygons):
    out = b"\x01" + struct.pack("<II", 6, len(polygons))
    return out + b"".join(_wkb_polygon(p) for p in polygons)


def _square(lng0, lat0, d):
    return [(lng0, lat0), (lng0 + d, lat0), (lng0 + d, lat0 + d), (lng0, lat0 + d), (lng0, lat0)]


# --- Decoder ---------------------------------------------------------------------------


def test_decode_point_with_and_without_envelope():
    assert osm.decode_geometry(_gp(_wkb_point(13.4, 52.5))) == ((13.4, 52.5), None)
    blob = _gp(_wkb_point(13.4, 52.5), envelope=(13.4, 13.4, 52.5, 52.5))
    assert osm.decode_geometry(blob)[0] == (13.4, 52.5)


def test_decode_big_endian_point():
    assert osm.decode_geometry(_gp(_wkb_point(13.4, 52.5, ">")))[0] == (13.4, 52.5)


def test_decode_polygon_and_multipolygon():
    sq = _square(13.4, 52.5, 0.01)
    _, polys = osm.decode_geometry(_gp(_wkb_polygon([sq]), envelope=(0, 1, 0, 1)))
    assert polys == [[sq]]
    _, polys = osm.decode_geometry(_gp(_wkb_multipolygon([[sq], [sq]])))
    assert len(polys) == 2


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        osm.decode_geometry(b"XX" + bytes(30))
    line = b"\x01" + struct.pack("<II", 2, 0)  # LineString: not needed, not supported
    with pytest.raises(ValueError, match="unsupported"):
        osm.decode_geometry(_gp(line))


def _make_gpkg(path, layers: dict[str, list[tuple[str, bytes]]]):
    con = sqlite3.connect(path)
    for layer, rows in layers.items():
        con.execute(
            f'CREATE TABLE "{layer}" (fid INTEGER PRIMARY KEY, fclass TEXT, name TEXT, geom BLOB)'
        )
        con.executemany(
            f'INSERT INTO "{layer}" (fclass, name, geom) VALUES (?, ?, ?)',
            [(fclass, None, blob) for fclass, blob in rows],
        )
    con.commit()
    con.close()


def test_read_layer_filters_by_fclass(tmp_path):
    path = tmp_path / "t.gpkg"
    _make_gpkg(
        path,
        {
            "gis_osm_pois_free": [
                ("cafe", _gp(_wkb_point(13.4, 52.5))),
                ("bench", _gp(_wkb_point(1, 2))),
            ]
        },
    )
    feats = list(osm.read_layer(path, "gis_osm_pois_free", frozenset({"cafe"})))
    assert [(f.fclass, f.point) for f in feats] == [("cafe", (13.4, 52.5))]


def test_amenity_categories_are_disjoint_except_beer_gardens():
    seen: dict[str, str] = {}
    for attr, (classes, radius) in osm.AMENITY_CATEGORIES.items():
        assert 0 < radius <= 1500
        for c in classes:
            if c in seen:
                assert c == "biergarten"  # both food and nightlife, deliberately
            seen[c] = attr


# --- Geometry helpers ------------------------------------------------------------------


def test_point_in_polygons_respects_holes():
    outer = _square(13.40, 52.50, 0.02)
    hole = _square(13.405, 52.505, 0.01)
    assert geo.point_in_polygons(13.401, 52.501, [[outer, hole]])
    assert not geo.point_in_polygons(13.41, 52.51, [[outer, hole]])  # in the hole
    assert not geo.point_in_polygons(13.5, 52.5, [[outer]])


def test_grid_index_count_and_nearest():
    idx = geo.GridIndex(100)
    for dx in (0, 50, 150, 400):
        idx.add(1000 + dx, 1000, "cafes")
    assert idx.count_within(1000, 1000, 100) == {"cafes": 2}
    assert idx.count_within(1000, 1000, 160) == {"cafes": 3}
    assert idx.nearest(1000, 1300, 1000) == pytest.approx(300)
    assert idx.nearest(9000, 9000, 500) == 500  # capped


def test_densify_ring_spacing():
    ring = _square(13.40, 52.50, 0.01)
    pts = list(geo.densify_ring(ring, 50))
    perimeter = 2 * 0.01 * (geo.M_PER_DEG_LNG + geo.M_PER_DEG_LAT)
    assert len(pts) == pytest.approx(perimeter / 50, rel=0.05)


# --- Access measurement ----------------------------------------------------------------


def test_grid_points_in_square():
    d = 0.01  # ~678 m x 1112 m
    pts = access.grid_points_in([_square(13.40, 52.50, d)], step=100)
    expected = (d * geo.M_PER_DEG_LNG / 100) * (d * geo.M_PER_DEG_LAT / 100)
    assert len(pts) == pytest.approx(expected, rel=0.2)
    assert all(x % 100 == 0 and y % 100 == 0 for x, y in pts)  # shared grid -> dedupe works


def test_resident_samples_assigns_points_to_planning_areas():
    plrs = {"A": [[_square(13.40, 52.50, 0.01)]], "B": [[_square(13.41, 52.50, 0.01)]]}
    residential = [[_square(13.402, 52.502, 0.004)], [_square(13.412, 52.502, 0.004)]]
    samples = access.resident_samples(residential, plrs)
    assert set(samples) == {"A", "B"}
    a_lng, _ = geo.to_lnglat(*samples["A"][0])
    assert 13.40 < a_lng < 13.41


def test_measure_plr_counts_and_distances():
    x0, y0 = geo.to_xy(13.40, 52.50)
    amen = access.amenity_index(
        [("cafe", 13.40, 52.5009), ("bar", 13.40, 52.5080), ("supermarket", 13.40, 52.52)]
    )
    water = geo.GridIndex(500)
    water.add(x0 + 300, y0)
    forest = geo.GridIndex(500)
    forest.add(x0 + 900, y0)
    transit = geo.GridIndex(500)
    transit.add(x0, y0 + 200)
    values, water_m, forest_m = access.measure_plr([(x0, y0)], amen, water, forest, transit)
    assert values["cafes"] == 1  # 100 m away, radius 500
    assert values["nightlife"] == 1  # ~890 m, radius 1000
    assert values["everyday"] == 0  # 2.2 km away
    assert values["water"] == pytest.approx(300)  # min(water, forest)
    assert (water_m, forest_m) == (pytest.approx(300), pytest.approx(900))
    assert values["transit"] == pytest.approx(200)


def test_edge_index_ignores_small_ponds():
    pond = [_square(13.40, 52.50, 0.0005)]  # ~34 x 56 m, < 1 ha
    lake = [_square(13.45, 52.50, 0.005)]  # ~34 ha
    idx = access.edge_index([pond, lake], 10_000)
    x, y = geo.to_xy(13.40, 52.50)
    assert idx.nearest(x, y, 3000) > 2000  # the pond doesn't count


def test_rapid_stops_keep_rail_and_tram_only():
    stations = {"s": ("S X", 52.5, 13.4), "b": ("Bus", 52.6, 13.5), "t": ("Tram", 52.7, 13.6)}
    rides = [
        {"route_type": "109", "from_station": "s", "to_station": "s"},
        {"route_type": "700", "from_station": "b", "to_station": "b"},
        {"route_type": "900", "from_station": "t", "to_station": "t"},
    ]
    assert access.rapid_stops(stations, rides) == [(13.4, 52.5), (13.6, 52.7)]


def test_compute_access_end_to_end(tmp_path):
    gpkg = tmp_path / "mini.gpkg"
    home = _square(13.400, 52.500, 0.003)
    _make_gpkg(
        gpkg,
        {
            "gis_osm_landuse_a_free": [
                ("residential", _gp(_wkb_polygon([home]))),
                ("forest", _gp(_wkb_polygon([_square(13.43, 52.50, 0.01)]))),
            ],
            "gis_osm_pois_free": [("cafe", _gp(_wkb_point(13.4015, 52.5015)))],
            "gis_osm_pois_a_free": [
                ("supermarket", _gp(_wkb_polygon([_square(13.401, 52.501, 0.0002)])))
            ],
            "gis_osm_water_a_free": [("water", _gp(_wkb_polygon([_square(13.38, 52.50, 0.005)])))],
        },
    )
    plrs = {
        "01100101": [[_square(13.39, 52.49, 0.03)]],
        "01100102": [[_square(13.60, 52.60, 0.01)]],  # residents, no residential land
        "01100103": [[_square(13.70, 52.60, 0.01)]],  # no residents: skipped
    }
    centroids = {"01100101": (52.505, 13.405), "01100102": (52.605, 13.605), "01100103": (0, 0)}
    pop = {"01100101": 1000, "01100102": 10, "01100103": 0}
    result = access.compute_access(gpkg, plrs, centroids, pop, [(13.4015, 52.503)])

    assert set(result) == {"01100101", "01100102"}
    a = result["01100101"]
    assert a.samples > 0 and a.home_centroid is not None
    assert a.values["cafes"] == 1 and a.values["everyday"] == 1  # polygon POI counted
    assert a.values["transit"] < 400
    assert a.water_m < a.forest_m  # the lake is closer than the forest
    fallback = result["01100102"]
    assert fallback.samples == 0 and fallback.home_centroid is None  # centroid fallback
