"""Berlin open data (ADR-0016): parsers, helpers, and the offline repository.

Pure tests always run. Tests marked `needs_raw` read the Berlin Visualized raw files and
skip when they aren't on this machine; `needs_build` tests read `make berlin-data` output.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from berlin import files
from berlin.geo import EARTH_RADIUS_M, haversine_one
from berlin.text import clean_house_number, search_key
from data import synthetic
from data.berlin import mietspiegel as M
from data.berlin import sources
from data.berlin.utm import utm_to_latlng


def _raw_available() -> bool:
    return (sources.raw_dir() / sources.BY_ID["living.rent_index_table_2026"].file).is_file()


needs_raw = pytest.mark.skipif(not _raw_available(), reason="Berlin Visualized raw files absent")
needs_build = pytest.mark.skipif(not files.is_built(), reason="run `make berlin-data` first")


# --- text and geometry helpers --------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    ["Choriner Straße 41", "choriner str. 41", "CHORINER STRASSE 41", "Choriner  Str 41"],
)
def test_search_key_folds_spellings_of_strasse(typed):
    assert search_key(typed) == "choriner str 41"


def test_search_key_folds_umlauts_and_punctuation():
    assert search_key("Müllerstr. 4A") == "muellerstr 4a"
    assert search_key("Straße des 17. Juni") == "str des 17 juni"
    assert search_key("Karl-Marx-Allee") == "karl marx allee"


def test_clean_house_number_strips_register_padding():
    assert clean_house_number("004A") == "4A"
    assert clean_house_number("010") == "10"
    assert clean_house_number("100") == "100"


def test_utm_matches_unfallatlas_published_wgs84():
    # One Unfallatlas row publishes both UTM32 (LINREFX/Y) and WGS84 for the same accident.
    lat, lng = utm_to_latlng(801025.7545, 5838496.962, zone=32)
    assert haversine_one(lat, lng, 52.612868733, 13.447041438) < 0.05  # metres


def test_haversine_one_degree_of_latitude():
    assert haversine_one(52.0, 13.4, 53.0, 13.4) == pytest.approx(math.pi * EARTH_RADIUS_M / 180)


# --- Mietspiegel parsing --------------------------------------------------------------


def test_size_bands():
    assert M._size_band("bis unter 35 m²") == (0, 35)
    assert M._size_band("40 m² bis unter 45 m²") == (40, 45)
    assert M._size_band("ab 120 m²") == (120, None)
    assert M._size_band("alle Wohnflächen") == (0, None)


def test_rent_table_rejects_partial_text():
    text = "1 bis 1918 bis unter 35 m² 6,53 € 9,58 € 13,43 €"
    with pytest.raises(M.ParseError, match="rows not found"):
        M.parse_rent_table_text(text)


def test_checklist_joins_wrapped_lines():
    assert M._join_lines(["Bad nicht beheizbar oder Elekt-", "roheizstrahler"]) == (
        "Bad nicht beheizbar oder Elektroheizstrahler"
    )
    assert M._join_lines(["Duschtasse", "oder -kabine"]) == "Duschtasse oder -kabine"
    assert M._join_lines(["Winter-/Dach-", "garten"]) == "Winter-/Dachgarten"


def test_checklist_ends_an_item_only_at_a_standalone_oder(monkeypatch):
    text = (
        "Merkmalgruppe 1: Bad/WC/Gäste-WC\n"
        "☐ Kein Handwaschbecken (Außenmaß 50 cm breit\noder weniger)\n"
        "oder\nthis line belongs to no item\n"
        "☐ Keine Duschmöglichkeit\n"
    )
    # An excerpt can't match the brochure's counts, so validate against the excerpt's own.
    monkeypatch.setattr(M, "EXPECTED_COUNTS", {(1, "-"): 2})
    monkeypatch.setattr(M, "ENERGY_THRESHOLDS", {"-": (), "+": ()})
    items = M.parse_checklist_columns([("-", text)])
    assert [i.text_de for i in items] == [
        "Kein Handwaschbecken (Außenmaß 50 cm breit oder weniger)",
        "Keine Duschmöglichkeit",
    ]
    assert [i.id for i in items] == ["bath-minus-01", "bath-minus-02"]


def test_checklist_rejects_wrong_counts():
    with pytest.raises(M.ParseError, match="counts"):
        M.parse_checklist_columns([("-", "Merkmalgruppe 1: Bad\n☐ Keine Duschmöglichkeit\n")])


@needs_raw
def test_rent_table_from_pdf_matches_the_brochure():
    rows = M.read_rent_table(sources.verified_path("living.rent_index_table_2026"))
    assert len(rows) == 189
    by_row = {r.row: r for r in rows}
    # Brochure No. 10.4 B: medium location, 1919–1949, 60 m² → row 81: 5.90 / 7.30 / 9.55.
    r81 = by_row[81]
    assert (r81.location, r81.period, r81.size_min, r81.size_max) == (
        "medium",
        "1919-1949",
        60,
        None,
    )
    assert (r81.low, r81.mean, r81.high) == (5.90, 7.30, 9.55)
    assert (by_row[3].low, by_row[3].mean, by_row[3].high) == (7.01, 9.27, 12.25)
    assert by_row[103].period == "1973-1990-east" and by_row[90].period == "1973-1985-west"
    assert by_row[63].size_max is None and by_row[63].period == "2010-2015"


@needs_raw
def test_checklist_from_pdf_has_all_83_items():
    items = M.read_checklist(sources.verified_path("living.rent_index_mietspiegel_2026"))
    assert len(items) == 83
    assert len({i.id for i in items}) == 83
    texts = {i.id: i.text_de for i in items}
    assert (
        texts["bath-plus-10"] == "Von der Badewanne getrennte zusätzliche Duschtasse oder -kabine"
    )
    assert texts["bath-minus-04"].endswith(
        "oder Elektroheizstrahler [bezieht sich nicht auf Gäste-WCs]"
    )
    assert texts["building-minus-08"].endswith("(Einbau/Installation der Heizanlage vor 1995)")
    assert {i.energy_kwh for i in items if i.energy_kwh} == {80, 100, 120, 145, 195, 235}


@needs_raw
def test_every_source_matches_its_checksum():
    for s in sources.SOURCES:
        sources.verified_path(s.id)


def test_verified_path_reports_missing_files(tmp_path):
    with pytest.raises(sources.SourceError, match="BERLIN_RAW_DIR"):
        sources.verified_path("living.schools", tmp_path)


# --- listings: building year ----------------------------------------------------------


def test_year_built_is_deterministic_and_in_range():
    listings = synthetic.generate_listings(100, seed=42)
    again = synthetic.generate_listings(100, seed=42)
    assert [x.year_built for x in listings] == [x.year_built for x in again]
    assert all(1870 <= x.year_built <= 2024 for x in listings)
    assert len({x.year_built // 10 for x in listings}) >= 8  # a real spread, not one decade


def test_year_built_leaves_every_other_field_unchanged(monkeypatch):
    with_year = synthetic.generate_listings(100, seed=42)
    monkeypatch.setattr(synthetic, "year_built_for", lambda _id: None)
    without = synthetic.generate_listings(100, seed=42)

    def strip(x):
        return {k: v for k, v in dataclasses.asdict(x).items() if k != "year_built"}

    assert [strip(x) for x in with_year] == [strip(x) for x in without]


# --- offline repository over the build ------------------------------------------------


@pytest.fixture(scope="module")
def local():
    from berlin.local import LocalBerlinData

    return LocalBerlinData()


@needs_build
def test_address_search_finds_the_design_sample_address(local):
    hits = local.search_addresses("choriner str. 41", limit=3)
    a = hits[0]
    assert (a.street, a.house_number, a.postcode) == ("Choriner Straße", "41", "10435")
    assert a.location_class == "good" and a.east
    assert local.address(a.id) == a
    assert local.area_at(a.lat, a.lng).plr_id == a.plr_id


@needs_build
def test_address_search_is_a_prefix_search_in_id_order(local):
    hits = local.search_addresses("Choriner Straße", limit=50)
    assert hits and all(h.street == "Choriner Straße" for h in hits)
    assert [h.id for h in hits] == sorted(h.id for h in hits)
    assert local.search_addresses("x") == []  # too short to search


@needs_build
def test_nearest_address_respects_district(local):
    a = local.search_addresses("choriner str. 41", limit=1)[0]
    assert local.nearest_address(a.lat, a.lng).street == "Choriner Straße"
    other = local.nearest_address(a.lat, a.lng, district="Mitte")
    assert other is not None and other.district == "Mitte"


@needs_build
def test_points_within_radius_are_sorted_and_inside(local):
    for layer in ("schools", "kitas", "playgrounds", "accidents"):
        rows = local.within(layer, 52.5300, 13.4100, 800)
        ds = [r["distance_m"] for r in rows]
        assert ds == sorted(ds) and all(d <= 800 for d in ds)


@needs_build
def test_nearest_stops_and_rail_filter(local):
    stops = local.nearest_stops(52.5300, 13.4100, limit=6)
    assert len(stops) == 6
    assert [s.distance_m for s in stops] == sorted(s.distance_m for s in stops)
    rail = local.nearest_stops(52.5300, 13.4100, limit=3, modes=frozenset({"sbahn", "ubahn"}))
    assert all({"sbahn", "ubahn"} & set(s.modes) for s in rail)


@needs_build
def test_nearest_park_is_zero_inside_a_park(local):
    hit = local.nearest_park(52.4730, 13.4030)  # middle of Tempelhofer Feld
    assert hit is not None and hit.distance_m == 0.0
    near = local.nearest_park(52.5300, 13.4100)
    assert near is not None and 0 < near.distance_m < 1500


@needs_build
def test_area_stats_cover_all_542_planning_areas(local):
    from berlin.measures import AREA_MEASURES

    stats = local.area_stats()
    assert len(stats) == 542
    for values in stats.values():
        for key in AREA_MEASURES:
            assert key in values
