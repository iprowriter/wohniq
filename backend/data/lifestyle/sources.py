"""Source registry for Lifestyle Match (stdlib only; embedded into regions.json).

One entry per publication we take numbers from. The UI shows `title`, `publisher`,
`data_year` and `caveat` next to every figure ("the data behind this"), so these are
written for users, not just for us. `licence=None` means the publisher doesn't state
one in the document we used — confirm before any redistribution of the raw files
(we only ship derived figures, with attribution).
"""

from __future__ import annotations

PKS = "pks_kriminalitaetsatlas"
REGISTER = "afs_einwohnerregister_2024"
OPERATING_COSTS = "senstadt_betriebskosten_2026"
IBB = "ibb_wohnungsmarktbericht_2025"
LOR = "senstadt_lor_2021"
UG_ATLAS = "umweltgerechtigkeitsatlas_2023_2024"
MMI = "mmi_studentisches_wohnen_sose_2025"
IBB_TABLES = "ibb_tabellenband_2025"
OSM = "openstreetmap_geofabrik"
VBB = "vbb_gtfs"

SOURCES: dict[str, dict] = {
    PKS: {
        "id": PKS,
        "title": "Kriminalitätsatlas Berlin — Fallzahlen und Häufigkeitszahlen 2016–2025",
        "publisher": "Polizei Berlin (LKA), Polizeiliche Kriminalstatistik",
        # The interactive atlas site was discontinued; data is published as XLSX by the
        # police (foreword, p. 1).
        "url": "https://www.berlin.de/polizei/",
        "licence": None,
        "data_year": "2023–2025",
        "used_for": "‘Kieztaten’ (neighbourhood offences) per 100,000 residents, "
        "averaged over 2023–2025, per Bezirksregion.",
        "caveat": "Reported offences per 100,000 registered residents. ‘Kieztaten’ are the "
        "police's neighbourhood-related offences (e.g. assault, threats, robbery, burglary, "
        "vandalism of cars). Areas many people visit (centre, nightlife, transport hubs) "
        "read higher than what residents experience; the police note a high rate can also "
        "reflect liveliness and popularity. Averaged over three years.",
    },
    REGISTER: {
        "id": REGISTER,
        "title": "Einwohnerregisterstatistik Berlin, 31. Dezember 2024 "
        "(Statistischer Bericht A I 16 – hj 2/24), Tabelle 2",
        "publisher": "Amt für Statistik Berlin-Brandenburg",
        "url": "https://www.statistik-berlin-brandenburg.de",
        "licence": "CC BY 3.0 DE",
        "data_year": "2024",
        "used_for": "Residents by age group per LOR-Planungsraum, summed to Bezirksregionen.",
        "caveat": "Registered main residences on 31 Dec 2024. We use age groups only; "
        "nationality and migration-background figures are deliberately not used.",
    },
    OPERATING_COSTS: {
        "id": OPERATING_COSTS,
        "title": "Berliner Betriebskostenübersicht 2026 (Abrechnungsjahr 2024)",
        "publisher": "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen",
        "url": "https://www.berlin.de/sen/wohnen/service/betriebskostenuebersicht/",
        "licence": None,
        "data_year": "2024",
        "used_for": "Average operating costs (cold + heating/hot water) to turn cold "
        "rent into warm rent.",
        "caveat": "Averages from larger housing companies' statements; individual flats vary.",
    },
    IBB: {
        "id": IBB,
        "title": "IBB Wohnungsmarktbericht 2025 — Zusammenfassung",
        "publisher": "Investitionsbank Berlin (IBB)",
        "url": "https://www.ibb.de/wohnungsmarktbericht",
        "licence": None,
        "data_year": "2025",
        "used_for": "Median asking rents (net cold) for Berlin, inner city and outer city.",
        "caveat": "Asking rents from listings (VALUE Marktdatenbank), not signed contracts; "
        "Berlin-wide, not per neighbourhood.",
    },
    LOR: {
        "id": LOR,
        "title": "Lebensweltlich orientierte Räume (LOR) 2021 — Planungsräume (WGS84)",
        "publisher": "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen / "
        "Amt für Statistik Berlin-Brandenburg",
        "url": "https://daten.berlin.de",
        "licence": None,
        "data_year": "2021",
        "used_for": "Planning-area boundaries (area, centre points) and the official "
        "‘Innere Stadt’ / ‘Äußere Stadt’ classification.",
        "caveat": "Region centre points are population-weighted, i.e. where people live, "
        "not the geometric middle of parks or rail yards.",
    },
    UG_ATLAS: {
        "id": UG_ATLAS,
        "title": "Umweltgerechtigkeitsatlas 2023/2024 (Broschüre), "
        "‘Aufschlüsselung der Planungsräume nach Belastungssituation’",
        "publisher": "Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt",
        "url": "https://www.berlin.de/umweltatlas/",
        "licence": None,
        "data_year": "noise 2022 · air 2023 · heat 2022 · green space 2020",
        "used_for": "Noise, air, heat and green-space burden class (low / medium / high) per "
        "Planungsraum, weighted by residents to Bezirksregionen.",
        "caveat": "Classes are relative to the rest of Berlin (lowest quarter = low, highest "
        "quarter = high), not absolute health thresholds. The atlas's social-disadvantage "
        "indicator is deliberately not used.",
    },
    MMI: {
        "id": MMI,
        "title": "Pressemitteilung: Neue Zahlen zu Studentischen Wohnkosten "
        "Sommersemester 2025 (10.03.2025)",
        "publisher": "Moses Mendelssohn Institut with WG-Gesucht.de",
        "url": "https://www.moses-mendelssohn-institut.de/aktuelles/SoSe2025",
        "licence": None,
        "data_year": "2025",
        "used_for": "Typical Berlin WG-room price and student housing allowances.",
        "caveat": "Average ‘ordinary’ WG room from listings; whole flats cost more.",
    },
    IBB_TABLES: {
        "id": IBB_TABLES,
        "title": "IBB Wohnungsmarktbericht 2025 — Tabellenband, Tab. 25 "
        "‘Angebotsmieten nach Bezirken 2025’",
        "publisher": "Investitionsbank Berlin (IBB); data: VALUE Marktdatenbank, "
        "RegioKontext GmbH",
        "url": "https://www.ibb.de/wohnungsmarktbericht",
        "licence": None,
        "data_year": "2025",
        "used_for": "Median asking rent (net cold) per district, and the range that 80% of "
        "offers fall into.",
        "caveat": "District medians from listings, not signed contracts. Neighbourhoods "
        "within a district differ; the range shows how much.",
    },
    OSM: {
        "id": OSM,
        "title": "OpenStreetMap — Geofabrik ‘berlin-latest-free’ GeoPackage",
        "publisher": "© OpenStreetMap contributors (ODbL 1.0), extract by Geofabrik GmbH",
        "url": "https://www.openstreetmap.org/copyright",
        "licence": "ODbL 1.0",
        "data_year": "2026",
        "used_for": "Cafés, shops, doctors, bars, culture and sport venues; residential "
        "land; lakes, rivers and forests.",
        "caveat": "Community-mapped: very complete in Berlin but not official. Distances are "
        "straight lines from homes, so real walks are a little longer.",
    },
    VBB: {
        "id": VBB,
        "title": "VBB GTFS timetable — weekday peak network (07:00–09:00)",
        "publisher": "VBB Verkehrsverbund Berlin-Brandenburg GmbH (open data)",
        "url": "https://www.vbb.de/vbbgtfs",
        "licence": None,
        "data_year": "2026",
        "used_for": "S-Bahn, U-Bahn, regional-rail and tram stops with peak-hour service.",
        "caveat": "Buses are not counted: almost everyone in Berlin lives near one.",
    },
}

# Berlin-wide figures transcribed from the documents above (not machine-extractable
# reliably from the PDFs, so they're pinned here with their page context and checked
# by tests against plausibility bounds).
CITY_FIGURES: dict[str, dict] = {
    "asking_rent_median": {
        "value": 15.78,
        "unit": "EUR/m² net cold",
        "source_id": IBB,
        "year": "2025",
        "note": "Berlin median asking rent (key figures table, p. 4; text p. 9).",
    },
    "asking_rent_inner_city": {
        "value": 19.22,
        "unit": "EUR/m² net cold",
        "source_id": IBB,
        "year": "2025",
        "note": "Median asking rent, inner city (section ‘Mietwohnungsmarkt’, p. 9).",
    },
    "asking_rent_outer_city": {
        "value": 13.01,
        "unit": "EUR/m² net cold",
        "source_id": IBB,
        "year": "2025",
        "note": "Median asking rent, outer city (section ‘Mietwohnungsmarkt’, p. 9).",
    },
    "operating_costs_cold": {
        "value": 1.93,
        "unit": "EUR/m² per month",
        "source_id": OPERATING_COSTS,
        "year": "2024",
        "note": "Average ‘kalte’ Betriebskosten.",
    },
    "operating_costs_warm": {
        "value": 1.50,
        "unit": "EUR/m² per month",
        "source_id": OPERATING_COSTS,
        "year": "2024",
        "note": "Average heating + hot water (‘warme’ Betriebskosten).",
    },
    "student_room_berlin": {
        "value": 650,
        "unit": "EUR/month",
        "source_id": MMI,
        "year": "2025",
        "note": "Average ordinary WG room in Berlin, summer semester 2025 (p. 5).",
    },
    "bafoeg_housing_allowance": {
        "value": 380,
        "unit": "EUR/month",
        "source_id": MMI,
        "year": "2025",
        "note": "BAföG housing allowance (Wohnkostenpauschale), raised from €360 (p. 4).",
    },
    "student_need_duesseldorf_table": {
        "value": 440,
        "unit": "EUR/month warm",
        "source_id": MMI,
        "year": "2025",
        "note": "Housing need of a student living away from home per the "
        "Düsseldorfer Tabelle, as cited (p. 4).",
    },
}

# IBB Tabellenband 2025, Tab. 25 (p. 13): median asking rent, net cold, EUR/m², and the
# range covering 80% of offers. Keys are the district names used in the crime atlas.
DISTRICT_RENTS: dict[str, tuple[float, float, float]] = {
    "Mitte": (20.00, 9.83, 28.69),
    "Friedrichshain-Kreuzberg": (19.40, 8.63, 28.00),
    "Pankow": (17.00, 9.20, 25.51),
    "Charlottenburg-Wilmersdorf": (19.17, 10.00, 28.20),
    "Spandau": (12.50, 7.43, 20.04),
    "Steglitz-Zehlendorf": (15.00, 8.88, 23.67),
    "Tempelhof-Schöneberg": (15.79, 8.37, 27.18),
    "Neukölln": (13.61, 7.43, 23.20),
    "Treptow-Köpenick": (15.60, 8.25, 22.01),
    "Marzahn-Hellersdorf": (11.56, 6.42, 18.52),
    "Lichtenberg": (13.33, 7.00, 21.44),
    "Reinickendorf": (12.80, 7.90, 21.26),
}
