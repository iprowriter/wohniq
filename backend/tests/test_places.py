"""Offline place lookup (work location → coordinates) and the VBB stops extractor."""

import csv
import io
import zipfile

import pytest

from data import fetch_vbb_stops
from enrich.places import PlaceIndex, load_stop_rows, normalize

# Real VBB stop-name shapes (coordinates rounded; fixture only).
ROWS = [
    {"name": "S+U Alexanderplatz", "lat": "52.5215", "lng": "13.4113", "location_type": ""},
    {
        "name": "S+U Alexanderplatz/Memhardstr.",
        "lat": "52.5230",
        "lng": "13.4110",
        "location_type": "",
    },
    {"name": "S+U Berlin Hauptbahnhof", "lat": "52.5256", "lng": "13.3691", "location_type": ""},
    {"name": "S+U Zoologischer Garten", "lat": "52.5069", "lng": "13.3327", "location_type": ""},
    {"name": "S+U Friedrichstr.", "lat": "52.5203", "lng": "13.3873", "location_type": ""},
    {"name": "S Südkreuz", "lat": "52.4755", "lng": "13.3656", "location_type": ""},
    {"name": "Pankow Kirche", "lat": "52.5690", "lng": "13.4020", "location_type": ""},
    # Bus stop named like a rail station — the S-Bahn station must win.
    {"name": "Ostkreuz", "lat": "52.4900", "lng": "13.4000", "location_type": ""},
    {"name": "S Ostkreuz", "lat": "52.5031", "lng": "13.4692", "location_type": ""},
]


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("S+U Alexanderplatz Bhf (Berlin)", "alexanderplatz"),
        ("U Alexanderplatz [Tram]", "alexanderplatz"),
        ("S+U Berlin Hauptbahnhof", "hauptbahnhof"),
        ("S+U Friedrichstr.", "friedrichstr"),
        ("Friedrichstraße", "friedrichstr"),
        ("Südkreuz", "sudkreuz"),
        ("Neukölln", "neukolln"),
        ("Beeskow, Ostkreuz", "beeskow ostkreuz"),  # other towns keep their prefix
    ],
)
def test_normalize(raw, key):
    assert normalize(raw) == key


@pytest.fixture
def index():
    return PlaceIndex(ROWS)


@pytest.mark.parametrize(
    ("query", "name"),
    [
        ("Alexanderplatz", "S+U Alexanderplatz"),
        ("alex", "S+U Alexanderplatz"),  # alias
        ("Hbf", "S+U Berlin Hauptbahnhof"),  # alias
        ("Zoo", "S+U Zoologischer Garten"),  # alias
        ("Friedrichstraße", "S+U Friedrichstr."),  # VBB abbreviation
        ("Sudkreuz", "S Südkreuz"),  # no umlaut
        ("Alexanderplats", "S+U Alexanderplatz"),  # typo → close match
        ("Ostkreuz", "S Ostkreuz"),  # rail station beats same-named bus stop
    ],
)
def test_resolves_stations(index, query, name):
    assert index.resolve(query).name == name


def test_kiez_names_resolve_to_kiez_centre(index):
    place = index.resolve("Kreuzberg")
    assert (place.source, place.name) == ("kiez", "Kreuzberg")


@pytest.mark.parametrize("query", ["Google office", "TU Berlin", "", None])
def test_unknown_places_resolve_to_none(index, query):
    assert index.resolve(query) is None


def test_without_stops_file_only_kiez_names_resolve(tmp_path):
    index = PlaceIndex(load_stop_rows(tmp_path / "missing.csv"))
    assert index.has_stops is False
    assert index.resolve("Alexanderplatz") is None
    assert index.resolve("Neukölln").source == "kiez"


def _gtfs_zip(path, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type", "parent_station"]
    )
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("stops.txt", "\ufeff" + buf.getvalue())  # BOM, as real feeds often have


def test_extract_stops_keeps_berlin_stations_and_drops_noise(tmp_path):
    gtfs = tmp_path / "gtfs.zip"
    _gtfs_zip(
        gtfs,
        [
            ["1", "S+U Alexanderplatz (Berlin)", "52.5215", "13.4113", "1", ""],
            ["2", "S+U Alexanderplatz Gleis 1", "52.5216", "13.4114", "0", "1"],  # platform
            ["3", "S+U Alexanderplatz Eingang", "52.5217", "13.4110", "2", ""],  # entrance
            ["4", "Hamburg Hbf", "53.5530", "10.0069", "1", ""],  # outside Berlin
            ["5", "U Kottbusser Tor (Berlin)", "52.4990", "13.4177", "", ""],
            ["6", "Broken", "not-a-number", "13.4", "", ""],
        ],
    )
    rows = fetch_vbb_stops.extract_stops(gtfs)
    assert [r["name"] for r in rows] == ["S+U Alexanderplatz (Berlin)", "U Kottbusser Tor (Berlin)"]

    target = tmp_path / "vbb" / "stops.csv"
    fetch_vbb_stops.write_stops(rows, target)
    index = PlaceIndex(load_stop_rows(target))
    assert index.resolve("Alexanderplatz").lat == pytest.approx(52.5215)
