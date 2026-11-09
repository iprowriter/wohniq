"""Lifestyle Match data build: parsers, join, and reproducibility of regions.json."""

import json
from dataclasses import fields

import pytest

from data.lifestyle import build_profiles as bp
from data.lifestyle import geo
from lifestyle.profiles import BUNDLE_PATH

# Layout-mode text as pypdf emits it: 2+ spaces between columns, 1 space in thousands.
HEADER = "Bezirksregion  gesamt  unter 6  6 - 15  15 - 18  18 - 27  27 - 45  45 - 55  55 - 65"
ROW_A = "01  10  01  01  3 580  165  203  49  466  1 219  385  376  717  1 711  1 581"
ROW_B = "01  10  01  02  2 034  91  105  27  204  799  242  304  262  921  1 093"
ROW_DASH = "01  10  02  05  10  –  2  –  3  5  –  –  –  4  1"


def test_parse_register_rows():
    rows = bp.parse_register_lines([HEADER, "Mitte", ROW_A, ROW_B, ROW_DASH, "Zusammen  397 004"])
    assert [r.planungsraum for r in rows] == ["01", "02", "05"]
    a = rows[0]
    assert a.region_key == "011001"
    assert a.total == 3580
    assert a.ages == (165, 203, 49, 466, 1219, 385, 376, 717)
    assert rows[2].ages == (0, 2, 0, 3, 5, 0, 0, 0)  # "–" means zero


def test_parse_register_drops_sex_and_nationality_columns():
    """Only total + age groups survive parsing; 'weiblich'/'Ausländer' are never stored."""
    assert {f.name for f in fields(bp.PlanningAreaRow)} == {
        "bezirk",
        "prognoseraum",
        "bezirksregion",
        "planungsraum",
        "total",
        "ages",
    }
    (row,) = bp.parse_register_lines([ROW_A])
    assert 1711 not in row.ages and 1581 not in row.ages


def test_parse_register_checksum_catches_misread_columns():
    # A thousands separator read as a column break shifts every cell: sum check fails.
    broken = "01  10  01  01  3 580  165  203  49  466  1  219  385  376  717  1 711"
    with pytest.raises(bp.BuildError):
        bp.parse_register_lines([broken])
    wrong_total = ROW_A.replace("3 580", "3 581")
    with pytest.raises(bp.BuildError, match="don't sum"):
        bp.parse_register_lines([wrong_total])


def _crime(values: dict[str, float], names: dict[str, str] | None = None) -> bp.CrimeTable:
    names = names or {}
    all_names = {"010000": "Mitte", **{k: names.get(k, f"Region {k}") for k in values}}
    kiez = {k: {y: v for y in bp.CRIME_YEARS} for k, v in values.items()}
    kiez[bp.CITY_KEY] = {y: 3000.0 for y in bp.CRIME_YEARS}
    all_names[bp.CITY_KEY] = bp.CITY_LABEL
    return bp.CrimeTable(names=all_names, kieztaten=kiez)


def _rows() -> list[bp.PlanningAreaRow]:
    return [
        bp.PlanningAreaRow("01", "10", "01", "01", 100, (10, 10, 0, 20, 30, 10, 10, 10)),
        bp.PlanningAreaRow("01", "10", "01", "02", 100, (0, 0, 0, 0, 50, 20, 20, 10)),
        bp.PlanningAreaRow("01", "10", "02", "03", 200, (20, 20, 10, 10, 60, 30, 30, 20)),
    ]


def test_build_bundle_aggregates_planning_areas():
    crime = _crime({"011001": 1000.0, "011002": 5000.0}, {"011002": "Südliche  Friedrichstadt"})
    bundle = bp.build_bundle(_rows(), crime)
    r1, r2 = bundle["regions"]
    assert r1["key"] == "011001" and r1["population"] == 200
    assert r1["measures"]["family"]["raw"] == 10.0  # (10+10+0+0+0+0)/200
    assert r1["measures"]["young_crowd"]["raw"] == 10.0  # 20/200
    assert r1["measures"]["safety"]["raw"] == 1000.0
    assert r1["district"] == "Mitte"
    assert r2["name"] == "Südliche Friedrichstadt"  # whitespace normalised
    assert bundle["references"]["safety"]["berlin"] == 3000.0


def test_build_bundle_refuses_a_partial_join():
    crime = _crime({"011001": 1000.0})  # 011002 missing from the crime atlas
    with pytest.raises(bp.BuildError, match="Join mismatch"):
        bp.build_bundle(_rows(), crime)


def test_region_key_filter():
    assert bp._is_region_key("011001")
    assert not bp._is_region_key("010000")  # district total
    assert not bp._is_region_key("019900")  # "nicht zuzuordnen"
    assert not bp._is_region_key("999999")  # city total


def test_read_crime_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for year in bp.CRIME_YEARS:
        ws = wb.create_sheet(f"HZ_{year}")
        ws.append(["Gesamtübersicht"])
        ws.append([])
        ws.append(
            ["LOR-Schlüssel (Bezirksregion)", "Bezeichnung (Bezirksregion)", "Raub", "Kieztaten"]
        )
        ws.append(["010000", "Mitte", 1, 2500])
        ws.append(["011001", "Tiergarten Süd", 1, 2000 + year])
        ws.append(["019900", "Bezirk (Mi), nicht zuzuordnen", "-", "-"])
        # 2023-style city row: no key, matched by its label.
        ws.append([None, bp.CITY_LABEL, 1, 3000])
    path = tmp_path / "crime.xlsx"
    wb.save(path)

    table = bp.read_crime_xlsx(path)
    assert table.kieztaten["011001"] == {y: 2000.0 + y for y in bp.CRIME_YEARS}
    assert table.kieztaten[bp.CITY_KEY][2023] == 3000.0
    assert "019900" not in table.kieztaten  # "-" rows skipped
    assert table.names["011001"] == "Tiergarten Süd"


# --- Geometry -------------------------------------------------------------------------


def _square(lng0, lat0, d):
    return [[lng0, lat0], [lng0 + d, lat0], [lng0 + d, lat0 + d], [lng0, lat0 + d], [lng0, lat0]]


def test_polygon_area_and_centroid_with_hole():
    d = 0.01  # ~0.68 km east-west, ~1.11 km north-south at Berlin's latitude
    outer = _square(13.40, 52.50, d)
    hole = _square(13.40, 52.50, d / 2)  # cut out the south-west quarter
    area_full, (lat_full, lng_full) = bp.polygon_area_centroid(
        {"type": "Polygon", "coordinates": [outer]}
    )
    area, (lat, lng) = bp.polygon_area_centroid({"type": "Polygon", "coordinates": [outer, hole]})
    assert area_full == pytest.approx(d * geo.M_PER_DEG_LNG * d * geo.M_PER_DEG_LAT)
    assert (lat_full, lng_full) == pytest.approx((52.505, 13.405))
    assert area == pytest.approx(area_full * 0.75)
    assert lat > lat_full and lng > lng_full  # centroid moves away from the hole
    multi = {"type": "MultiPolygon", "coordinates": [[outer], [_square(13.50, 52.50, d)]]}
    assert bp.polygon_area_centroid(multi)[0] == pytest.approx(2 * area_full)


def _feature(plr_id, bzr_id, lng0, stadtraum="Innere Stadt", finhalt=None):
    geom = {"type": "MultiPolygon", "coordinates": [[_square(lng0, 52.50, 0.01)]]}
    area, _ = bp.polygon_area_centroid(geom)
    return {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "plr_id": plr_id,
            "bzr_id": bzr_id,
            "finhalt": finhalt if finhalt is not None else area,
            "stadtraum_name": stadtraum,
        },
    }


def test_read_lor_geojson_validates(tmp_path):
    path = tmp_path / "lor.geojson"

    def write(*features):
        path.write_text(json.dumps({"type": "FeatureCollection", "features": list(features)}))

    write(
        _feature("01100101", "011001", 13.40), _feature("01100102", "011001", 13.42, "Äußere Stadt")
    )
    areas = bp.read_lor_geojson(path)
    assert areas["01100101"].inner_city and not areas["01100102"].inner_city
    assert areas["01100101"].centroid == pytest.approx((52.505, 13.405))

    write(_feature("01100101", "011001", 13.40, finhalt=1.0))  # geometry ≠ published area
    with pytest.raises(bp.BuildError, match="published"):
        bp.read_lor_geojson(path)
    write(_feature("01100101", "022002", 13.40))  # PLR key doesn't nest in its BZR
    with pytest.raises(bp.BuildError, match="nest"):
        bp.read_lor_geojson(path)
    write(_feature("01100101", "011001", 13.40, stadtraum="Mond"))
    with pytest.raises(bp.BuildError, match="Stadtraum"):
        bp.read_lor_geojson(path)


# --- Umweltgerechtigkeitsatlas table --------------------------------------------------

ANCHORS = [261, 364, 404, 440, 479, 519]  # x of the six column headers (page 49)


def test_decode_full_row():
    # Helmholtzplatz: noise 1, air 3, heat 3, green 3, social 2 -> 3 high cells.
    runs = [(261, 3), (361, 1), (400, 3), (440, 3), (480, 3), (519, 2)]
    assert bp.decode_ug_row(runs, ANCHORS) == [3, 1, 3, 3, 3, 2]


def test_decode_row_with_gaps_uses_positions():
    # Pankower Tor: only Mehrfachbelastung, air and heat are printed.
    runs = [(261, 1), (400, 3), (440, 1)]
    assert bp.decode_ug_row(runs, ANCHORS) == [1, None, 3, 1, None, None]
    # No high cells -> the Mehrfachbelastung column is simply empty.
    runs = [(361, 2), (400, 2), (440, 1), (479, 1), (519, 2)]
    assert bp.decode_ug_row(runs, ANCHORS) == [None, 2, 2, 1, 1, 2]


@pytest.mark.parametrize(
    "runs, message",
    [
        ([(261, 2), (361, 3), (400, 1), (440, 1), (480, 1), (519, 1)], "Checksum"),
        ([(361, 2), (365, 2)], "Can't place"),  # two runs in one column
        ([(300, 2)], "Can't place"),  # between columns
        ([(361, 4)], "Out-of-range"),
    ],
)
def test_decode_row_rejects_bad_rows(runs, message):
    with pytest.raises(bp.BuildError, match=message):
        bp.decode_ug_row(runs, ANCHORS)


def test_district_key_ignores_soft_hyphens():
    assert bp.district_key("FRIEDRICHSHAIN\xadKREUZBERG") == bp.district_key(
        "Friedrichshain-Kreuzberg"
    )


# --- Full assembly with geometry + environment -----------------------------------------


def _areas() -> dict[str, bp.PlanningArea]:
    return {
        "01100101": bp.PlanningArea("01100101", "011001", 1e6, (52.50, 13.40), True),
        "01100102": bp.PlanningArea("01100102", "011001", 1e6, (52.52, 13.40), False),
        "01100203": bp.PlanningArea("01100203", "011002", 2e6, (52.60, 13.50), False),
    }


def test_build_bundle_with_geometry_and_environment():
    crime = _crime({"011001": 1000.0, "011002": 5000.0})
    ug = {
        "01100101": bp.UgRow("01100101", (1, 3, 2, 1)),
        "01100102": bp.UgRow("01100102", (3, 3, 2, None)),  # green not reported here
        "01100203": bp.UgRow("01100203", (2, 2, 2, 2)),
    }
    bundle = bp.build_bundle(_rows(), crime, _areas(), ug)
    r1, r2 = bundle["regions"]
    # Both PLRs have 100 residents -> centroid halfway; half live in the inner city.
    assert r1["centroid"] == [52.51, 13.40]
    assert r1["area_km2"] == 2.0 and r1["density_per_km2"] == 100
    assert r1["inner_city_share"] == 0.5
    assert r1["rent"]["raw"] == 20.00  # district median (Mitte)
    quiet = r1["measures"]["quiet"]
    assert quiet["raw"] == 2.0 and quiet["shares"] == {"best": 50.0, "middle": 0.0, "worst": 50.0}
    # Green covers only 50% of r1's residents: exactly the minimum, so it's kept.
    assert r1["measures"]["green"]["raw"] == 1.0
    assert bundle["references"]["quiet"]["low"] == 1.0
    assert r2["inner_city_share"] == 0.0 and r2["rent"]["raw"] == 20.00


def test_build_bundle_skips_indicators_with_thin_coverage():
    crime = _crime({"011001": 1000.0, "011002": 5000.0})
    ug = {
        "01100101": bp.UgRow("01100101", (1, 1, 1, 1)),
        "01100102": bp.UgRow("01100102", (1, 1, 1, 1)),
        # 01100203 (all of region 011002) missing, e.g. a publication erratum
    }
    bundle = bp.build_bundle(_rows(), crime, _areas(), ug)
    assert "quiet" not in bundle["regions"][1]["measures"]  # unscored, not guessed
    assert "quiet" in bundle["regions"][0]["measures"]


def test_build_bundle_refuses_geometry_register_mismatch():
    crime = _crime({"011001": 1000.0, "011002": 5000.0})
    areas = _areas()
    del areas["01100203"]
    with pytest.raises(bp.BuildError, match="disagree"):
        bp.build_bundle(_rows(), crime, areas)


def test_ug_row_keeps_no_social_column():
    assert len(bp.UgRow("01100101", (1, 1, 1, 1)).classes) == len(bp.UG_INDICATORS) == 4


# --- Reproducibility -------------------------------------------------------------------


@pytest.mark.slow
def test_rebuild_from_raw_files_reproduces_shipped_bundle(tmp_path):
    """If the official files are present locally, the build must be reproducible."""
    for module in ("openpyxl", "pypdf", "pdfplumber"):
        pytest.importorskip(module)
    globs = (bp.CRIME_GLOB, bp.REGISTER_GLOB, bp.LOR_GLOB, bp.UG_GLOB, bp.OSM_GLOB, bp.GTFS_GLOB)
    if not all(list(bp.RAW_DIR.glob(g)) for g in globs):
        pytest.skip("raw source files not present (see data/lifestyle/raw/README.md)")
    out, shapes = tmp_path / "regions.json", tmp_path / "regions_geo.json"
    bp.main(["--out", str(out), "--shapes-out", str(shapes)])
    assert json.loads(out.read_text()) == json.loads(BUNDLE_PATH.read_text())
    from lifestyle.shapes import SHAPES_PATH

    assert json.loads(shapes.read_text()) == json.loads(SHAPES_PATH.read_text())


# --- Region outlines -------------------------------------------------------------------


def test_dissolve_merges_edge_matched_neighbours():
    left = [_square(13.40, 52.50, 0.01)]
    right = [_square(13.41, 52.50, 0.01)]
    rings = geo.dissolve([left, right])
    assert len(rings) == 1  # the shared border cancelled out
    (poly,) = geo.rings_to_polygons(rings)
    area, _ = geo.polygons_area_centroid([poly])
    single, _ = geo.polygons_area_centroid([left])
    assert area == pytest.approx(2 * single)


def test_dissolve_keeps_holes_and_separate_parts():
    outer = _square(13.40, 52.50, 0.03)
    hole = _square(13.41, 52.51, 0.01)
    ring_with_hole = [outer, list(reversed(hole))]
    island = [_square(13.60, 52.60, 0.01)]
    polys = geo.rings_to_polygons(geo.dissolve([ring_with_hole, island]))
    assert sorted(len(p) for p in polys) == [1, 2]  # island; outer + hole


def test_dissolve_rejects_ambiguous_topology():
    # Two squares touching only at a corner: that vertex has two outgoing edges.
    a = [_square(13.40, 52.50, 0.01)]
    b = [_square(13.41, 52.51, 0.01)]
    with pytest.raises(ValueError, match="branches"):
        geo.dissolve([a, b])


def test_simplify_ring_drops_collinear_points_and_stays_closed():
    ring = [
        (13.40, 52.50),
        (13.405, 52.50),
        (13.41, 52.50),
        (13.41, 52.51),
        (13.40, 52.51),
        (13.40, 52.50),
    ]
    out = geo.simplify_ring(ring, 5)
    assert (13.405, 52.5) not in out
    assert out[0] == out[-1] and len(out) == 5


def test_shipped_region_shapes_preserve_area():
    from lifestyle.profiles import get_bundle
    from lifestyle.shapes import get_shapes

    shapes = get_shapes()
    for region in get_bundle().regions:
        area, _ = geo.polygons_area_centroid(shapes.shapes[region.key].polygons)
        assert area / 1e6 == pytest.approx(region.area_km2, rel=0.015)
        assert shapes.region_of(*region.centroid) == region.key  # centre lies inside


def test_region_centre_is_snapped_inside_a_concave_region():
    """Two far-apart planning areas: their weighted mean lies between them, outside both."""
    from data.lifestyle.access import PlrAccess

    west = [[_square(13.30, 52.50, 0.01)]]  # one polygon = [outer ring]
    east = [[_square(13.50, 52.50, 0.01)]]
    areas = {
        "01100101": bp.PlanningArea("01100101", "011001", 1e6, (52.505, 13.305), True, west),
        "01100102": bp.PlanningArea("01100102", "011001", 1e6, (52.505, 13.505), True, east),
        "01100203": bp.PlanningArea(
            "01100203", "011002", 1e6, (52.605, 13.405), False, [[_square(13.40, 52.60, 0.01)]]
        ),
    }
    attrs = ("cafes", "everyday", "nightlife", "culture", "sport", "water", "transit")

    def values(v):
        return dict.fromkeys(attrs, v)

    access = {
        "01100101": PlrAccess(5, values(1.0), 1, 1, (52.505, 13.305), (52.5051, 13.3049)),
        "01100102": PlrAccess(5, values(2.0), 1, 1, (52.505, 13.505), (52.5052, 13.5051)),
        "01100203": PlrAccess(5, values(9.0), 1, 1, (52.605, 13.405), (52.605, 13.405)),
    }
    rows = [
        bp.PlanningAreaRow("01", "10", "01", "01", 100, (10, 10, 0, 20, 30, 10, 10, 10)),
        bp.PlanningAreaRow("01", "10", "01", "02", 101, (0, 0, 0, 0, 51, 20, 20, 10)),
        bp.PlanningAreaRow("01", "10", "02", "03", 200, (20, 20, 10, 10, 60, 30, 30, 20)),
    ]
    crime = _crime({"011001": 1000.0, "011002": 5000.0})
    bundle = bp.build_bundle(rows, crime, areas, None, access)
    lat, lng = bundle["regions"][0]["centroid"]
    # The plain weighted mean would be ≈ 13.405 (between the two squares); snapped to
    # the anchor of the slightly more populous eastern area.
    assert (lat, lng) == (52.5052, 13.5051)
