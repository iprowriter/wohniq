"""Berlin Neighbourhoods — parsers for the official source files (pure, offline).

Small excerpts in the exact shape the publications print them; each parser also checks
itself against figures the publication states, which these tests exercise too.
"""

import pytest

from data.neighborhoods.parse import (
    CITY_KEY,
    ParseError,
    crime_rates_from_sheets,
    parse_accident_rows,
    parse_bzr_csv,
    parse_mss_lines,
    parse_school_tables,
)

# --- Kriminalitätsatlas ------------------------------------------------------------------

HEADER = (
    "LOR-Schlüssel (Bezirksregion)",
    "Bezeichnung (Bezirksregion)",
    "Straftaten \n-insgesamt-",
    "Raub",
    "Körper-verletzungen \n-insgesamt-",
    "Diebstahl von Kraftwagen",
    "Diebstahl \nan/aus Kfz",
    "Fahrrad-\ndiebstahl",
    "Wohnraum-\neinbruch",
    "Kieztaten",
)


def _sheet(rows):
    return [("Gesamtübersicht",) + (None,) * 9, HEADER, *rows]


def test_crime_rates_are_means_over_years_and_sum_car_columns():
    sheets = {
        2023: _sheet(
            [
                ("011001", "Tiergarten Süd", 100, 10, 20, 1, 2, 5, 3, 50),
                (None, "Berlin (PKS gesamt)", 50, 5, 10, 1, 1, 2, 2, 20),  # key missing (2023)
            ]
        ),
        2024: _sheet(
            [
                ("011001", "Tiergarten Süd", 200, 20, 40, 3, 4, 7, 5, 70),
                ("999999", "Berlin (PKS gesamt)", 70, 7, 12, 1, 1, 2, 2, 40),
            ]
        ),
    }
    table = crime_rates_from_sheets(sheets, years=(2023, 2024))
    r = table.rates["011001"]
    assert r["total"] == 150 and r["kiez"] == 60 and r["robbery"] == 15
    assert r["car_crime"] == (3 + 7) / 2  # (1+2) and (3+4)
    assert table.rates[CITY_KEY]["kiez"] == 30
    assert table.names["011001"] == "Tiergarten Süd"


def test_crime_rows_with_dashes_are_skipped_not_zeroed():
    sheets = {
        2025: _sheet(
            [
                ("019900", "Mitte (nicht zuordenbar)", "-", "-", "-", "-", "-", "-", "-", "-"),
                ("999999", "Berlin (PKS gesamt)", 70, 7, 12, 1, 1, 2, 2, 40),
            ]
        )
    }
    table = crime_rates_from_sheets(sheets, years=(2025,))
    assert "019900" not in table.rates


def test_crime_missing_column_fails_loudly():
    sheet = [HEADER[:-1] + ("Something else",)]
    with pytest.raises(ParseError, match="kiez"):
        crime_rates_from_sheets({2025: sheet}, years=(2025,))


# --- MSS 2023 ------------------------------------------------------------------------------

MSS_PYPDF = """1 / 11
Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen Berlin
Nummer Name
01100101 Stülerstraße 3.561 2 mittel +/- stabil 2+/- Status mittel , Dynamik stabil
01200627 Zillesiedlung 3.424 4 sehr niedrig + positiv 4+ Status sehr niedrig , Dynamik positiv
07200308 Volkspark (Rudolph-Wilde-Park) 10.560 2 mittel +/- stabil 2+/- Status mittel
03300515 Blankenburger Süden 50
03300515 - Blankenburger Süden (EW unter 300)
10100205 - Gewerbegebiet Bitterfelder Straße (Ausreißerproblematik)"""

MSS_PDFTOTEXT = (
    "01100102   Großer Tiergarten                                 2.002    1         hoch"
    "         +/-     stabil       1+/-      Status hoch , Dynamik stabil\n"
    "06200418   Landweg                                                0                 "
    "     Im MSS-Indexverfahren nicht berücksichtigt (unter 300 EW)."
)


def test_mss_rows_pypdf_layout():
    rows = parse_mss_lines(MSS_PYPDF.split("\n"))
    assert [r.plr for r in rows] == ["01100101", "01200627", "07200308", "03300515"]
    assert rows[1].status == 4 and rows[1].population == 3424
    assert rows[2].name == "Volkspark (Rudolph-Wilde-Park)"  # parentheses in names
    assert rows[3].status is None and rows[3].population == 50  # not indexed
    assert rows[0].region_key == "011001"


def test_mss_rows_pdftotext_layout():
    rows = parse_mss_lines(MSS_PDFTOTEXT.split("\n"))
    assert [(r.plr, r.status, r.population) for r in rows] == [
        ("01100102", 1, 2002),
        ("06200418", None, 0),
    ]


def test_mss_class_must_match_label():
    with pytest.raises(ParseError, match="doesn't match"):
        parse_mss_lines(["01100101 Stülerstraße 3.561 3 mittel +/- stabil 2+/- Status mittel"])


def test_mss_duplicate_planning_area_fails():
    line = "01100101 Stülerstraße 3.561 2 mittel +/- stabil 2+/- Status mittel , Dynamik stabil"
    with pytest.raises(ParseError, match="duplicate"):
        parse_mss_lines([line, line])


# --- Blickpunkt Schule -----------------------------------------------------------------------

# The real 2025/26 figures (tables 3.2.3 and 5.1.2), in pypdf's text layout: the stacked
# bar chart 5.1.2 comes out series by series (no qualification, BBR, eBBR, MSA, Abitur).
CHART = {
    "none": [119, 184, 293, 296, 356, 315, 176, 302, 301, 108, 183, 189],
    "bbr": [117, 141, 167, 214, 196, 219, 158, 188, 210, 131, 153, 132],
    "ebbr": [165, 171, 212, 313, 206, 305, 144, 294, 262, 173, 251, 162],
    "msa": [822, 499, 1040, 959, 705, 904, 1209, 892, 769, 904, 1110, 741],
    "abitur": [1635, 884, 987, 709, 1238, 880, 1705, 1233, 798, 1986, 1171, 983],
}
TABLE_323 = """3.2.3  Schüler/-innen nach Förderprognose in den Bezirken im Schuljahr 2024/25
Bezirk
Anzahl in % Anzahl in % Anzahl in %
CW 1.207 52,3 760 32,9 343 14,8 2.310
FK 1.356 58,6 741 32,0 216 9,3 2.313
Li 1.259 49,0 1.136 44,2 175 6,8 2.570
MH 1.214 44,6 1.288 47,3 221 8,1 2.723
Mi 1.195 42,7 1.309 46,8 296 10,6 2.800
Nk 1.021 38,7 1.336 50,7 278 10,6 2.635
Pa 2.234 62,3 1.115 31,1 235 6,6 3.584
Rd 1.011 42,9 1.120 47,6 224 9,5 2.355
Sp 893 38,1 1.272 54,3 179 7,6 2.344
SZ 1.419 55,8 836 32,8 290 11,4 2.545
TS 1.298 52,0 1.041 41,7 158 6,3 2.497
TK 1.184 48,0 939 38,1 344 13,9 2.467
Insgesamt 15.291 49,1 11.817 37,9 2.765 8,9 31.143

3.3 Schüler/-innen der 7. Jahrgangsstufe an Integrierten Sekundarschulen"""


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".") if n >= 1000 and n % 7 else str(n)  # both styles occur


def _report_text(chart=CHART) -> str:
    numbers = "\n".join(_fmt(n) for q in ("none", "bbr", "ebbr", "msa", "abitur") for n in chart[q])
    return (
        TABLE_323
        + "\n… (5.1.2).\n5.1.2  Schüler/-innen an allgemeinen Schulen nach Schulabschluss in den "
        "Bezirken, Schuljahr 2024/25\n \n"
        + numbers
        + "\n0% 10% 20% 30% 40% 50% 60% 70% 80% 90% 100%\nCW\nFK\n"
    )


def test_school_tables_parse_and_reproduce_the_reports_percentages():
    t = parse_school_tables(_report_text())
    assert round(t.share("Steglitz-Zehlendorf", "abitur"), 1) == 60.1
    assert round(t.share("Marzahn-Hellersdorf", "abitur"), 1) == 28.5
    assert t.leavers["Pankow"]["abitur"] == 1705
    assert t.gymnasium_pct["Pankow"] == 62.3 and t.gymnasium_pct_berlin == 49.1
    assert round(t.share_berlin("abitur"), 1) == 44.0


def test_school_chart_shift_is_caught_by_the_text_checks():
    shifted = {q: v[1:] + v[:1] for q, v in CHART.items()}  # districts off by one
    with pytest.raises(ParseError, match="report says"):
        parse_school_tables(_report_text(shifted))


def test_school_chart_with_missing_numbers_fails():
    short = {**CHART, "abitur": CHART["abitur"][:-1]}
    with pytest.raises(ParseError, match="60 numbers"):
        parse_school_tables(_report_text(short))


# --- Unfallatlas ---------------------------------------------------------------------------

ACCIDENT_CSV = (
    "\ufeffUIDENTSTLAE;ULAND;UREGBEZ;UKREIS;UGEMEINDE;UJAHR;UMONAT;USTUNDE;UWOCHENTAG;"
    "UKATEGORIE;UART;UTYP1;ULICHTVERH;IstStrassenzustand;IstRad;IstPKW;IstFuss;IstKrad;"
    "IstGkfz;IstSonstige;LINREFX;LINREFY;XGCSWGS84;YGCSWGS84;PLST\n"
    "a;11;0;03;003;2025;11;20;1;3;8;1;2;0;0;1;0;0;0;0;1,0;2,0;13,447041438;52,612868733;1\n"
    "b;11;0;01;001;2025;1;8;2;2;5;3;0;0;1;0;0;0;0;0;1,0;2,0;13,4;52,5;1\n"
    "c;11;0;01;001;2025;1;8;2;1;5;3;0;0;0;0;1;0;0;0;1,0;2,0;13,41;52,51;1\n"
    "d;01;0;60;007;2025;05;15;6;3;5;3;0;0;0;1;0;0;0;0;1,0;2,0;10,19;53,92;1\n"
)


def test_accidents_berlin_only_with_decimal_commas():
    accidents, year = parse_accident_rows(ACCIDENT_CSV.splitlines())
    assert year == 2025 and len(accidents) == 3  # Schleswig-Holstein row dropped
    a = accidents[0]
    assert a.lng == pytest.approx(13.447041438) and a.lat == pytest.approx(52.612868733)
    assert not a.severe and accidents[1].severe and accidents[2].category == 1
    assert accidents[1].bike and accidents[2].pedestrian


def test_accidents_mixed_years_fail():
    mixed = ACCIDENT_CSV.replace("a;11;0;03;003;2025", "a;11;0;03;003;2024")
    with pytest.raises(ParseError, match="one accident year"):
        parse_accident_rows(mixed.splitlines())


# --- LOR Bezirksregionen ------------------------------------------------------------------


def test_bzr_csv_gives_names_and_familiar_wider_area():
    rows = parse_bzr_csv(
        [
            "bzr_id,bzr_name,pgr_id,pgr_name,bez,finhalt,stand",
            "011001,Tiergarten Süd,0110,Zentrum,01 - Mitte,5172480.9,01.12.2021",
            "023003,Nördliche Luisenstadt,0230,Kreuzberg Nord,02 - Friedrichshain-Kreuzberg,1,x",
        ]
    )
    assert rows["023003"].area_group == "Kreuzberg Nord"
    assert rows["023003"].district == "Friedrichshain-Kreuzberg"
    assert rows["011001"].name == "Tiergarten Süd"


# --- Bodenrichtwerte --------------------------------------------------------------------------

from data.neighborhoods.parse import (  # noqa: E402
    density_class,
    income_report_from_words,
    land_zones_from_geojson,
    merge_number_words,
)


def _zone(brwid, use, brw, gfz, stichtag="2026-01-01"):
    ring = [[13.4, 52.5], [13.41, 52.5], [13.41, 52.51], [13.4, 52.51], [13.4, 52.5]]
    return {
        "type": "Feature",
        "properties": {
            "brwid": brwid,
            "nutzung": use,
            "brw": brw,
            "gfz": gfz,
            "stichtag": stichtag,
            "bezirk": "Mitte",
        },
        "geometry": {"type": "MultiPolygon", "coordinates": [[ring]]},
    }


def _zones(extra=()):
    feats = [_zone(str(i), "W - Wohngebiet", 500 + i, 0.4) for i in range(120)]
    return {"type": "FeatureCollection", "features": feats + list(extra)}


def test_land_zones_keep_residential_uses_only():
    zones, date = land_zones_from_geojson(
        _zones(
            [
                _zone("g1", "G - Gewerbe", 300, 1.0),
                _zone("k1", "M1 - Kerngebiet", 9000, 4.5),
                _zone(
                    "f1",
                    "LF-F - Flächen der Land-o. Forstwirtschaft - forstwirtschaftliche Fläche",
                    5,
                    None,
                ),
            ]
        )
    )
    ids = {z.zone_id for z in zones}
    assert date == "2026-01-01" and "k1" in ids and "g1" not in ids and "f1" not in ids


def test_density_class_never_mixes_houses_and_flats():
    assert density_class("W - Wohngebiet", 0.4) == "houses"
    assert density_class("W - Wohngebiet", 0.7) == "houses"
    assert density_class("W - Wohngebiet", 1.0) == "flats"
    assert density_class("W-EFH - Wohnbaufläche - Ein- und Zweifamilienhäuser", None) == "houses"
    assert density_class("M1 - Kerngebiet", None) == "flats"


def test_land_zones_reject_missing_values_mixed_dates_and_duplicates():
    with pytest.raises(ParseError, match="no Bodenrichtwert"):
        land_zones_from_geojson(_zones([_zone("x", "W - Wohngebiet", None, 0.4)]))
    with pytest.raises(ParseError, match="reference date"):
        land_zones_from_geojson(_zones([_zone("x", "W - Wohngebiet", 500, 0.4, "2025-01-01")]))
    with pytest.raises(ParseError, match="duplicate"):
        land_zones_from_geojson(_zones([_zone("1", "W - Wohngebiet", 500, 0.4)]))


# --- Lohn- und Einkommensteuerstatistik, table 1 ---------------------------------------------


def _words(line: str, top: float) -> list[dict]:
    """Lay out a printed row like the PDF: groups joined by "~" get a 1.5 pt thin space,
    tokens separated by spaces a 10 pt column gap."""
    out, x = [], 20.0
    for token in line.split(" "):
        for j, part in enumerate(token.split("~")):
            if j:
                x += 1.5
            w = 6.0 * len(part)
            out.append({"text": part, "x0": x, "x1": x + w, "top": top})
            x += w
        x += 10.0
    return out


TABLE_1 = [
    "betrag der Einkünfte 1~945~538 2~017~622 104 84~739~956 91~117~107 108 16~554~068 "
    "17~265~536 104,3 19,5 18,9",
    "Besteuerte 1~425~544 1~486~632 104 47~391~248 51~917~447 "
    "110 8~893~232 9~568~872 108 18,8 18,4",
    "0 – 5~000 217~150 207~528 96 383~023 352~867 92 26~397 23~373 89 6,9 6,6",
    "5~000 – 50~000 1~100~000 1~250~000 114 30~000~000 33~000~000 110 1~000 2~000 200 3,3 6,1",
    "50~000 – 125~000 415~940 459~481 110 30~702~824 33~696~262 "
    "110 5~990~367 6~515~761 109 19,5 19,2",
    "125~000 und mehr 86~522 100~613 116 22~652~209 24~067~978 "
    "106 7~397~838 7~514~584 102 32,7 31,2",
]


def test_merge_number_words_joins_thin_spaced_groups_only():
    assert merge_number_words(_words("Besteuerte 1~425~544 1~486~632 104", 0)) == [
        "Besteuerte",
        "1425544",
        "1486632",
        "104",
    ]


def test_income_report_totals_brackets_and_median():
    words = [w for i, line in enumerate(TABLE_1) for w in _words(line, 100 + 12 * i)]
    r = income_report_from_words(words, 2022)
    assert (r.taxpayers, r.income_keur) == (2_017_622, 91_117_107)
    assert round(r.mean_eur) == 45_161
    assert [b.low for b in r.brackets] == [0, 5_000, 50_000, 125_000]
    assert r.brackets[-1].high is None
    assert r.median_bracket().low == 5_000


def test_income_report_brackets_must_add_up():
    broken = TABLE_1[:-1] + [TABLE_1[-1].replace("100~613", "100~614")]
    words = [w for i, line in enumerate(broken) for w in _words(line, 100 + 12 * i)]
    with pytest.raises(ParseError, match="add up"):
        income_report_from_words(words, 2022)
