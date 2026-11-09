"""Fixed commute destinations for Lifestyle Match (v1: a curated list, no free text).

A fixed list keeps the feature private by construction: the user picks an id, so no
typed address ever reaches the server, a log or a third-party API. It also makes
commute times precomputable at build time (see build_profiles), so results are
identical on every machine.

Coordinates are taken from data, not typed from memory:
  * campuses — centroid of the main campus polygon in OpenStreetMap (Geofabrik extract
    2026-11-08), feature name in `derived_from`;
  * hubs — the station's coordinates in the VBB GTFS feed (stop id in `derived_from`).
"""

from __future__ import annotations

DESTINATIONS: list[dict] = [
    # --- Universities and campuses (OSM polygon centroids) -------------------------
    {
        "id": "tu_berlin",
        "name": "TU Berlin (main campus, Charlottenburg)",
        "short": "TU Berlin",
        "kind": "university",
        "lat": 52.5117,
        "lng": 13.32677,
        "derived_from": "OSM university ‘Technische Universität Berlin’ (32 ha campus)",
    },
    {
        "id": "hu_berlin",
        "name": "Humboldt-Universität (Campus Mitte)",
        "short": "HU Berlin",
        "kind": "university",
        "lat": 52.51817,
        "lng": 13.39307,
        "derived_from": "OSM university ‘Humboldt-Universität zu Berlin - Campus Mitte’",
    },
    {
        "id": "hu_adlershof",
        "name": "Adlershof (HU campus & WISTA science park)",
        "short": "Adlershof",
        "kind": "university",
        "lat": 52.43166,
        "lng": 13.53053,
        "derived_from": "OSM university ‘Humboldt-Universität Campus Adlershof’",
    },
    {
        "id": "fu_berlin",
        "name": "Freie Universität (Dahlem)",
        "short": "FU Berlin",
        "kind": "university",
        "lat": 52.45421,
        "lng": 13.29287,
        "derived_from": "OSM university ‘Freie Universität Berlin’ (31 ha core campus)",
    },
    {
        "id": "htw_berlin",
        "name": "HTW Berlin (Campus Wilhelminenhof)",
        "short": "HTW Berlin",
        "kind": "university",
        "lat": 52.45626,
        "lng": 13.52591,
        "derived_from": "OSM university ‘Hochschule für Technik und Wirtschaft Berlin "
        "Campus Wilhelminenhof’",
    },
    {
        "id": "bht_berlin",
        "name": "Berliner Hochschule für Technik (Wedding)",
        "short": "BHT",
        "kind": "university",
        "lat": 52.54445,
        "lng": 13.35282,
        "derived_from": "OSM university ‘Berliner Hochschule für Technik’",
    },
    {
        "id": "udk_berlin",
        "name": "Universität der Künste (Hardenbergstraße)",
        "short": "UdK Berlin",
        "kind": "university",
        "lat": 52.50618,
        "lng": 13.32858,
        "derived_from": "OSM university ‘Universität der Künste Berlin’ (4.3 ha)",
    },
    {
        "id": "hwr_berlin",
        "name": "HWR Berlin (Campus Schöneberg)",
        "short": "HWR Berlin",
        "kind": "university",
        "lat": 52.48514,
        "lng": 13.33781,
        "derived_from": "OSM college ‘Hochschule für Wirtschaft und Recht Berlin – "
        "Campus Schöneberg’",
    },
    {
        "id": "charite_mitte",
        "name": "Charité Campus Mitte",
        "short": "Charité Mitte",
        "kind": "university",
        "lat": 52.52592,
        "lng": 13.37745,
        "derived_from": "OSM hospital ‘Campus Charité Mitte’",
    },
    # --- City hubs (VBB station coordinates) ----------------------------------------
    {
        "id": "alexanderplatz",
        "name": "Alexanderplatz",
        "short": "Alexanderplatz",
        "kind": "hub",
        "lat": 52.521512,
        "lng": 13.411267,
        "derived_from": "VBB station de:11000:900100003 ‘S+U Alexanderplatz Bhf’",
    },
    {
        "id": "potsdamer_platz",
        "name": "Potsdamer Platz",
        "short": "Potsdamer Platz",
        "kind": "hub",
        "lat": 52.509358,
        "lng": 13.376547,
        "derived_from": "VBB station de:11000:900100020 ‘S+U Potsdamer Platz Bhf’",
    },
    {
        "id": "hauptbahnhof",
        "name": "Berlin Hauptbahnhof",
        "short": "Hauptbahnhof",
        "kind": "hub",
        "lat": 52.525605,
        "lng": 13.369075,
        "derived_from": "VBB station de:11000:900003201 ‘S+U Berlin Hauptbahnhof’",
    },
    {
        "id": "zoo_city_west",
        "name": "Zoologischer Garten / City West (Kurfürstendamm)",
        "short": "Zoo / City West",
        "kind": "hub",
        "lat": 52.506921,
        "lng": 13.332707,
        "derived_from": "VBB station de:11000:900023201 ‘S+U Zoologischer Garten Bhf’",
    },
]
