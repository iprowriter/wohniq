"""Source registry for Berlin Neighbourhoods (embedded into neighborhoods.json).

New publications are described here; figures reused from the Lifestyle Match bundle keep
that bundle's source entries (copied at build time, so both features cite identically).
`licence=None` = the document we used doesn't state one; we ship derived figures only,
with attribution.
"""

from __future__ import annotations

PKS = "pks_kriminalitaetsatlas"
UNFALLATLAS = "unfallatlas_2025"
MSS = "mss_2023"
SCHOOLS = "blickpunkt_schule_2026"
OSM_NEW = "openstreetmap_geofabrik_2026_11_12"
LAND_VALUES = "bodenrichtwerte_2026"
INCOME_TAX = "afs_lohnsteuer_2022"

# Reused from data/lifestyle/regions.json (ids as there).
REUSED = (
    "openstreetmap_geofabrik",
    "vbb_gtfs",
    "umweltgerechtigkeitsatlas_2023_2024",
    "ibb_tabellenband_2025",
    "afs_einwohnerregister_2024",
    "senstadt_lor_2021",
)

SOURCES: dict[str, dict] = {
    PKS: {
        "id": PKS,
        "title": "Kriminalitätsatlas Berlin — Fallzahlen und Häufigkeitszahlen 2016–2025",
        "publisher": "Polizei Berlin (LKA), Polizeiliche Kriminalstatistik",
        "url": "https://www.berlin.de/polizei/",
        "licence": None,
        "data_year": "2023–2025",
        "used_for": "Offence rates per 100,000 residents (neighbourhood offences, assault, "
        "robbery, burglary, bike and car crime, all offences), mean of 2023–2025, per "
        "Bezirksregion.",
        "caveat": "Reported offences per 100,000 registered residents. Areas many people visit "
        "(centre, nightlife, transport hubs) read higher than what residents experience; the "
        "police note a high rate can also reflect liveliness and popularity.",
    },
    UNFALLATLAS: {
        "id": UNFALLATLAS,
        "title": "Unfallatlas — Unfallorte 2025 (Open Data)",
        "publisher": "Statistische Ämter des Bundes und der Länder",
        "url": "https://unfallatlas.statistikportal.de",
        "licence": "Datenlizenz Deutschland – Namensnennung – 2.0",
        "data_year": "2025",
        "used_for": "Location and severity of every police-recorded road accident with "
        "personal injury in Berlin, counted per Bezirksregion.",
        "caveat": "Only accidents with personal injury. Accidents count where they happened; "
        "main roads carry through traffic.",
    },
    MSS: {
        "id": MSS,
        "title": "Monitoring Soziale Stadtentwicklung 2023 — Tabelle 1: Gesamtindex Soziale "
        "Ungleichheit (Status/Dynamik-Index) auf Planungsraum-Ebene",
        "publisher": "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin",
        "url": "https://www.berlin.de/sen/sbw/stadtdaten/stadtwissen/"
        "monitoring-soziale-stadtentwicklung/",
        "licence": None,
        "data_year": "2022 (status on 31 Dec 2022)",
        "used_for": "Status-Index class (1 high – 4 very low) and residents of each of the "
        "542 planning areas, weighted by residents up to Bezirksregionen.",
        "caveat": "The status index combines four indicators of residents' social and "
        "economic situation (e.g. unemployment, welfare receipt). It describes averages, "
        "not people. The Senate doesn't index 6 planning areas (under 300 residents or "
        "statistical outliers); they're left out of the average.",
    },
    SCHOOLS: {
        "id": SCHOOLS,
        "title": "Blickpunkt Schule, Bericht 2025/2026 — Tab. 3.2.3 (Förderprognose) and "
        "Abb. 5.1.2 (Schulabschlüsse in den Bezirken)",
        "publisher": "Senatsverwaltung für Bildung, Jugend und Familie, Referat I C",
        "url": "https://www.bildungsstatistik.berlin.de",
        "licence": None,
        "data_year": "2024/25",
        "used_for": "Per district: school leavers from general schools by qualification, and "
        "primary pupils by secondary-school recommendation.",
        "caveat": "District figures, counted where the school is (pupils may live in another "
        "district). The report notes that school populations differ a lot between districts.",
    },
    OSM_NEW: {
        "id": OSM_NEW,
        "title": "OpenStreetMap — Berlin extract (Geofabrik, free GeoPackage), 2026-11-12",
        "publisher": "© OpenStreetMap contributors; extract by Geofabrik GmbH",
        "url": "https://download.geofabrik.de/europe/germany/berlin.html",
        "licence": "ODbL 1.0",
        "data_year": "2026",
        "used_for": "Hospitals, doctors, pharmacies, schools, Kitas, playgrounds, parks, "
        "stops, parking ticket machines, car parks and streets, measured from 100 m sample "
        "points on residential land.",
        "caveat": "As complete as volunteer mapping; straight-line distances understate real "
        "walks a little.",
    },
    LAND_VALUES: {
        "id": LAND_VALUES,
        "title": "Bodenrichtwerte zum 01.01.2026 (Vektordaten, WGS84)",
        "publisher": "Gutachterausschuss für Grundstückswerte in Berlin",
        "url": "https://www.berlin.de/gutachterausschuss/",
        "licence": None,
        "data_year": "2026 (reference date 1 Jan 2026)",
        "used_for": "Standard land value (EUR/m² of plot) of the residential, core and mixed "
        "zones that the area's home sample points lie in.",
        "caveat": "Bodenrichtwerte are typical land prices for a zone, not values of "
        "individual properties. Land for houses and for blocks of flats are different "
        "markets, so each home is only compared with land of the same kind.",
    },
    INCOME_TAX: {
        "id": INCOME_TAX,
        "title": "Statistischer Bericht L IV 3 – j / 22: Lohn- und Einkommensteuerstatistik "
        "im Land Berlin 2022, Tabelle 1",
        "publisher": "Amt für Statistik Berlin-Brandenburg",
        "url": "https://www.statistik-berlin-brandenburg.de",
        "licence": "CC BY 3.0 DE",
        "data_year": "2022",
        "used_for": "Berlin-wide taxpayers and total income (Gesamtbetrag der Einkünfte), "
        "shown as the city reference for income.",
        "caveat": "Berlin as a whole only; the report has no district breakdown.",
    },
}
