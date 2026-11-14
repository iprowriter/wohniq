"""Parsers for the official files behind Berlin Neighbourhoods (build time only).

Each function turns one publication into plain Python data and checks it against
something the publication itself states (row counts, totals, quoted percentages), so a
new edition with a changed layout fails loudly instead of producing wrong numbers.

    read_crime_breakdown   Kriminalitätsatlas XLSX  → offence rates per Bezirksregion
    parse_mss_lines        MSS 2023 table 1 (PDF)   → social-status class per Planungsraum
    parse_school_tables    Blickpunkt Schule (PDF)  → school-leaver qualifications and
                                                      Gymnasium recommendations per district
    parse_accident_rows    Unfallatlas CSV          → injury accidents in Berlin with coordinates
    read_bzr_meta          LOR 2021 Bezirksregionen → names + Prognoseraum per region

The text-level functions (`parse_*`) are pure and unit-tested with small excerpts; the
`read_*` wrappers only open files.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


class ParseError(RuntimeError):
    """A source file doesn't look like the edition the parser was written for."""


# --- Districts ---------------------------------------------------------------------------

DISTRICTS = {  # two-digit LOR prefix -> district name (as in the Lifestyle bundle)
    "01": "Mitte",
    "02": "Friedrichshain-Kreuzberg",
    "03": "Pankow",
    "04": "Charlottenburg-Wilmersdorf",
    "05": "Spandau",
    "06": "Steglitz-Zehlendorf",
    "07": "Tempelhof-Schöneberg",
    "08": "Neukölln",
    "09": "Treptow-Köpenick",
    "10": "Marzahn-Hellersdorf",
    "11": "Lichtenberg",
    "12": "Reinickendorf",
}

# Abbreviations used in the Blickpunkt Schule tables, in the order the tables print them.
SCHOOL_DISTRICT_CODES = {
    "CW": "Charlottenburg-Wilmersdorf",
    "FK": "Friedrichshain-Kreuzberg",
    "Li": "Lichtenberg",
    "MH": "Marzahn-Hellersdorf",
    "Mi": "Mitte",
    "Nk": "Neukölln",
    "Pa": "Pankow",
    "Rd": "Reinickendorf",
    "Sp": "Spandau",
    "SZ": "Steglitz-Zehlendorf",
    "TS": "Tempelhof-Schöneberg",
    "TK": "Treptow-Köpenick",
}


def _de_number(text: str) -> float:
    """German number: '1.207' -> 1207, '52,3' -> 52.3."""
    return float(text.replace(".", "").replace(",", "."))


# --- Kriminalitätsatlas ------------------------------------------------------------------

CRIME_YEARS = (2023, 2024, 2025)
CITY_KEY = "999999"
CITY_LABEL = "Berlin (PKS gesamt)"

# Our id -> column headings in the HZ sheets (whitespace-normalised; several columns
# are summed, e.g. car theft + theft from/of cars).
CRIME_COLUMNS: dict[str, tuple[str, ...]] = {
    "total": ("Straftaten -insgesamt-",),
    "kiez": ("Kieztaten",),
    "violence": ("Körper-verletzungen -insgesamt-",),
    "robbery": ("Raub",),
    "burglary": ("Wohnraum- einbruch",),
    "bike_theft": ("Fahrrad- diebstahl",),
    "car_crime": ("Diebstahl von Kraftwagen", "Diebstahl an/aus Kfz"),
}


@dataclass(frozen=True)
class CrimeRates:
    names: dict[str, str]  # key -> official name (regions, districts, city)
    # key -> our id -> mean Häufigkeitszahl (offences per 100,000 residents) over the years
    rates: dict[str, dict[str, float]]
    years: tuple[int, ...]


def crime_rates_from_sheets(
    sheets: dict[int, list[tuple]], years: Iterable[int] = CRIME_YEARS
) -> CrimeRates:
    """Mean rate per offence group over `years`, from the rows of the `HZ_<year>` sheets."""
    years = tuple(years)
    names: dict[str, str] = {}
    per_year: dict[str, dict[str, list[float]]] = {}
    for year in years:
        rows = sheets.get(year)
        if rows is None:
            raise ParseError(f"missing sheet HZ_{year}")
        header_idx = next(
            (i for i, r in enumerate(rows) if r and str(r[0] or "").startswith("LOR-Schlüssel")),
            None,
        )
        if header_idx is None:
            raise ParseError(f"HZ_{year}: header row not found")
        header = [" ".join(str(c or "").split()) for c in rows[header_idx]]
        cols: dict[str, list[int]] = {}
        for cid, headings in CRIME_COLUMNS.items():
            try:
                cols[cid] = [header.index(h) for h in headings]
            except ValueError:
                raise ParseError(f"HZ_{year}: column for {cid!r} not found in {header}") from None
        for r in rows[header_idx + 1 :]:
            key = str(r[0] or "").strip()
            if not key and str(r[1] or "").strip() == CITY_LABEL:  # key missing in 2023
                key = CITY_KEY
            if not re.fullmatch(r"\d{6}", key):
                continue
            values = {}
            for cid, idx in cols.items():
                cells = [r[i] for i in idx]
                if not all(isinstance(c, int | float) for c in cells):
                    break  # "-" for rows the police can't assign to a region
                values[cid] = float(sum(cells))
            else:
                names.setdefault(key, str(r[1]).strip())
                for cid, v in values.items():
                    per_year.setdefault(key, {}).setdefault(cid, []).append(v)
    rates = {
        key: {cid: statistics.fmean(vs) for cid, vs in by_id.items() if len(vs) == len(years)}
        for key, by_id in per_year.items()
    }
    rates = {k: v for k, v in rates.items() if len(v) == len(CRIME_COLUMNS)}
    if CITY_KEY not in rates:
        raise ParseError("no Berlin-wide row found")
    return CrimeRates(names=names, rates=rates, years=years)


def read_crime_breakdown(path: Path, years: Iterable[int] = CRIME_YEARS) -> CrimeRates:
    from openpyxl import load_workbook  # build-time dependency only

    years = tuple(years)
    wb = load_workbook(path, read_only=True, data_only=True)
    sheets = {}
    for year in years:
        name = f"HZ_{year}"
        if name not in wb.sheetnames:
            raise ParseError(f"{path.name}: missing sheet {name}")
        sheets[year] = list(wb[name].iter_rows(values_only=True))
    return crime_rates_from_sheets(sheets, years)


# --- Monitoring Soziale Stadtentwicklung 2023 ---------------------------------------------

STATUS_CLASSES = {"hoch": 1, "mittel": 2, "niedrig": 3, "sehr niedrig": 4}


@dataclass(frozen=True)
class MssRow:
    plr: str  # 8-digit Planungsraum key (LOR 01/2023); first 6 digits = Bezirksregion
    name: str
    population: int  # residents on 31.12.2022
    status: int | None  # 1 high … 4 very low; None = not indexed by the Senate (< 300 EW etc.)

    @property
    def region_key(self) -> str:
        return self.plr[:6]


# An indexed row: "01100101 Stülerstraße 3.561 2 mittel +/- stabil …". A row the Senate
# didn't index (< 300 residents, outlier) ends after the population (pypdf) or continues
# with "Im MSS-Indexverfahren nicht berücksichtigt" (pdftotext).
_MSS_ROW = re.compile(
    r"^(?P<plr>\d{8})\s+(?P<name>(?!-\s)[^\d]+?)\s+(?P<ew>\d{1,3}(?:\.\d{3})*)"
    r"(?:\s+(?P<cls>[1-4])\s+(?P<label>sehr niedrig|niedrig|mittel|hoch)\s.*"
    r"|\s+Im MSS-Indexverfahren.*|\s*)$"
)


def parse_mss_lines(lines: Iterable[str]) -> list[MssRow]:
    """Rows of MSS 2023 table 1 (one per Planungsraum).

    Each row's class number must agree with its label ("3 niedrig"), which catches a
    column shift in the PDF text.
    """
    rows: list[MssRow] = []
    seen: set[str] = set()
    for line in lines:
        m = _MSS_ROW.match(line.strip())
        if not m:
            continue
        plr = m["plr"]
        if plr in seen:
            raise ParseError(f"duplicate Planungsraum {plr}")
        seen.add(plr)
        status = None
        if m["cls"]:
            status = int(m["cls"])
            if STATUS_CLASSES[m["label"]] != status:
                raise ParseError(f"{plr}: class {status} doesn't match label {m['label']!r}")
        rows.append(MssRow(plr, m["name"].strip(), int(_de_number(m["ew"])), status))
    return rows


def read_mss_pdf(path: Path) -> list[MssRow]:
    from pypdf import PdfReader  # build-time dependency only

    lines = [ln for page in PdfReader(path).pages for ln in (page.extract_text() or "").split("\n")]
    rows = parse_mss_lines(lines)
    if not 500 <= len(rows) <= 600:
        raise ParseError(f"{path.name}: parsed {len(rows)} Planungsräume; expected ~542")
    total = sum(r.population for r in rows)
    if not 3_500_000 <= total <= 4_200_000:  # Berlin's registered population
        raise ParseError(f"{path.name}: residents sum to {total:,}; expected ~3.8 million")
    return rows


# --- Blickpunkt Schule 2025/26 -------------------------------------------------------------

QUALIFICATIONS = ("none", "bbr", "ebbr", "msa", "abitur")  # chart order, left to right


@dataclass(frozen=True)
class SchoolTables:
    # district name -> qualification -> school leavers (general schools, 2024/25; table 5.1.2)
    leavers: dict[str, dict[str, int]]
    # district name -> % of pupils leaving primary school with a Gymnasium/ISS
    # recommendation ("Förderprognose", 2024/25; table 3.2.3)
    gymnasium_pct: dict[str, float]
    gymnasium_pct_berlin: float

    def share(self, district: str, qualification: str) -> float:
        row = self.leavers[district]
        return 100 * row[qualification] / sum(row.values())

    def share_berlin(self, qualification: str) -> float:
        total = sum(sum(r.values()) for r in self.leavers.values())
        return 100 * sum(r[qualification] for r in self.leavers.values()) / total


# Figures the report's text quotes for table 5.1.2: the chart numbers must reproduce them.
LEAVER_CHECKS = (
    ("Steglitz-Zehlendorf", "abitur", 60.1),
    ("Charlottenburg-Wilmersdorf", "abitur", 57.2),
    ("Marzahn-Hellersdorf", "abitur", 28.5),
    ("Steglitz-Zehlendorf", "none", 3.3),
    ("Mitte", "none", 13.2),
    ("Neukölln", "none", 12.0),
)
LEAVER_CHECK_BERLIN_NONE = 8.7


def _section(text: str, heading: str, end: str) -> str:
    """Text between a table heading (regex) and the next `end` (regex)."""
    m = re.search(heading, text)
    if m is None:
        raise ParseError(f"section {heading!r} not found")
    stop = re.compile(end).search(text, m.end())
    return text[m.end() : stop.start() if stop else None]


def parse_school_tables(text: str) -> SchoolTables:
    """Tables 3.2.3 and 5.1.2 from the report's extracted text (pypdf)."""
    codes = list(SCHOOL_DISTRICT_CODES)

    # 3.2.3 — a real table: "CW 1.207 52,3 760 32,9 343 14,8 2.310"
    sec = _section(text, r"3\.2\.3\s+Schüler", r"\n\s*3\.3\s")
    gym: dict[str, float] = {}
    berlin_gym = None
    for line in sec.split("\n"):
        parts = line.split()
        if len(parts) == 8 and parts[0] in SCHOOL_DISTRICT_CODES:
            gym[SCHOOL_DISTRICT_CODES[parts[0]]] = _de_number(parts[2])
        elif len(parts) == 8 and parts[0] == "Insgesamt":
            berlin_gym = _de_number(parts[2])
    if len(gym) != 12 or berlin_gym is None:
        raise ParseError(f"table 3.2.3: found {len(gym)} districts")

    # 5.1.2 — a stacked bar chart: 5 series × 12 districts, printed series by series,
    # followed by the axis ("0% 10% …") and the district codes.
    sec = _section(text, r"5\.1\.2\s+Schüler", r"\n\s*0%")
    numbers = [
        int(_de_number(t)) for t in re.findall(r"(?m)^\s*(\d{1,3}(?:\.\d{3})*|\d+)\s*$", sec)
    ]
    if len(numbers) != len(QUALIFICATIONS) * 12:
        raise ParseError(f"chart 5.1.2: expected 60 numbers, found {len(numbers)}")
    leavers = {
        SCHOOL_DISTRICT_CODES[code]: {
            q: numbers[qi * 12 + di] for qi, q in enumerate(QUALIFICATIONS)
        }
        for di, code in enumerate(codes)
    }
    tables = SchoolTables(leavers, gym, berlin_gym)
    for district, q, expected in LEAVER_CHECKS:
        got = round(tables.share(district, q), 1)
        if got != expected:
            raise ParseError(f"chart 5.1.2: {district} {q} = {got}%, report says {expected}%")
    if round(tables.share_berlin("none"), 1) != LEAVER_CHECK_BERLIN_NONE:
        raise ParseError("chart 5.1.2: Berlin share without qualification doesn't match the text")
    return tables


def read_school_pdf(path: Path) -> SchoolTables:
    from pypdf import PdfReader

    pages = PdfReader(path).pages
    text = "\n".join(
        p.extract_text() or ""
        for p in pages
        if any(m in (p.extract_text() or "") for m in ("3.2.3", "5.1.2"))
    )
    return parse_school_tables(text)


# --- Unfallatlas -------------------------------------------------------------------------

BERLIN_LAND = "11"


@dataclass(frozen=True)
class Accident:
    lng: float
    lat: float
    category: int  # 1 killed, 2 seriously injured, 3 slightly injured
    bike: bool
    pedestrian: bool

    @property
    def severe(self) -> bool:
        return self.category in (1, 2)


def parse_accident_rows(lines: Iterable[str]) -> tuple[list[Accident], int]:
    """Berlin accidents (ULAND 11) from the semicolon CSV; returns (accidents, year)."""
    reader = csv.DictReader(lines, delimiter=";")
    out: list[Accident] = []
    years: set[str] = set()
    for row in reader:
        row = {k.lstrip("\ufeff"): v for k, v in row.items()}
        if row["ULAND"] != BERLIN_LAND:
            continue
        years.add(row["UJAHR"])
        out.append(
            Accident(
                lng=float(row["XGCSWGS84"].replace(",", ".")),
                lat=float(row["YGCSWGS84"].replace(",", ".")),
                category=int(row["UKATEGORIE"]),
                bike=row["IstRad"] == "1",
                pedestrian=row["IstFuss"] == "1",
            )
        )
    if len(years) != 1:
        raise ParseError(f"expected one accident year, found {sorted(years)}")
    return out, int(years.pop())


def read_accidents(path: Path) -> tuple[list[Accident], int]:
    """From the published ZIP (csv/Unfallorte_<year>_LR_BasisDLM.csv) or a bare CSV."""
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
            with zf.open(name) as fh:
                return parse_accident_rows(io.TextIOWrapper(fh, encoding="utf-8-sig"))
    with path.open(encoding="utf-8-sig") as fh:
        return parse_accident_rows(fh)


# --- LOR 2021 Bezirksregionen ---------------------------------------------------------------


@dataclass(frozen=True)
class BzrMeta:
    key: str
    name: str
    area_group: str  # Prognoseraum name, e.g. "Kreuzberg Nord" — a familiar wider area
    district: str


def parse_bzr_csv(lines: Iterable[str]) -> dict[str, BzrMeta]:
    out: dict[str, BzrMeta] = {}
    for row in csv.DictReader(lines):
        key = row["bzr_id"].strip()
        if not re.fullmatch(r"\d{6}", key):
            raise ParseError(f"bad Bezirksregion key {key!r}")
        out[key] = BzrMeta(
            key=key,
            name=row["bzr_name"].strip(),
            area_group=row["pgr_name"].strip(),
            district=DISTRICTS[key[:2]],
        )
    return out


def read_bzr_meta(path: Path) -> dict[str, BzrMeta]:
    with path.open(encoding="utf-8-sig") as fh:
        return parse_bzr_csv(fh)


# --- Bodenrichtwerte (Gutachterausschuss Berlin, vector data) --------------------------------

# Zone uses people live in: residential areas, plus core and mixed areas (inner-city blocks
# of flats above shops). Commercial, special-use, farm and forest zones are left out.
RESIDENTIAL_USES = {
    "W - Wohngebiet",
    "W-EFH - Wohnbaufläche - Ein- und Zweifamilienhäuser",
    "M1 - Kerngebiet",
    "M2 - Mischgebiet",
}
HOUSES_MAX_GFZ = 0.7  # the Gutachterausschuss doesn't convert prices within GFZ 0.2–0.7

DensityClass = str  # "houses" | "flats"


@dataclass(frozen=True)
class LandZone:
    zone_id: str
    polygons: list
    value: float  # Bodenrichtwert, EUR per m² of plot
    gfz: float | None  # typical floor-area ratio the value refers to
    use: str
    density: DensityClass


def density_class(use: str, gfz: float | None) -> DensityClass:
    """Houses (detached/semi-detached, GFZ ≤ 0.7) or flats (multi-storey).

    The Gutachterausschuss calls converting a value between these sub-markets
    "fachlich unzulässig" (Erläuterungen zu den Bodenrichtwerten, § 4), so land is only
    ever compared with land of the same class.
    """
    if use.startswith("W-EFH"):
        return "houses"
    if gfz is None:
        return "flats" if use.startswith(("M1", "M2")) else "houses"
    return "houses" if gfz <= HOUSES_MAX_GFZ else "flats"


def land_zones_from_geojson(data: dict) -> tuple[list[LandZone], str]:
    """Residential Bodenrichtwert zones and their reference date (stichtag)."""
    from data.lifestyle import geo

    zones: list[LandZone] = []
    dates: set[str] = set()
    for i, f in enumerate(data.get("features", [])):
        p = f["properties"]
        dates.add(str(p.get("stichtag")))
        if p.get("nutzung") not in RESIDENTIAL_USES:
            continue
        value = p.get("brw")
        if not isinstance(value, int | float) or value <= 0:
            raise ParseError(f"zone {p.get('brwid', i)}: no Bodenrichtwert")
        gfz = p.get("gfz")
        zones.append(
            LandZone(
                zone_id=str(p.get("brwid") or i),
                polygons=geo.geojson_polygons(f["geometry"]),
                value=float(value),
                gfz=float(gfz) if gfz is not None else None,
                use=p["nutzung"],
                density=density_class(p["nutzung"], gfz),
            )
        )
    if len(dates) != 1:
        raise ParseError(f"expected one reference date, found {sorted(dates)}")
    if len({z.zone_id for z in zones}) != len(zones):
        raise ParseError("duplicate zone ids (brwid)")
    if len(zones) < 100:
        raise ParseError(f"only {len(zones)} residential zones; expected ~900")
    return zones, dates.pop()


def read_land_zones(path: Path) -> tuple[list[LandZone], str]:
    import json

    return land_zones_from_geojson(json.loads(path.read_text(encoding="utf-8")))


# --- Lohn- und Einkommensteuerstatistik (Statistischer Bericht L IV 3) -------------------------


@dataclass(frozen=True)
class IncomeBracket:
    low: int  # EUR, inclusive
    high: int | None  # EUR, exclusive; None = open-ended
    taxpayers: int
    income_keur: int  # Gesamtbetrag der Einkünfte, 1,000 EUR


@dataclass(frozen=True)
class IncomeReport:
    year: int
    taxpayers: int  # with a positive total income
    income_keur: int
    brackets: list[IncomeBracket]

    @property
    def mean_eur(self) -> float:
        return 1000 * self.income_keur / self.taxpayers

    def median_bracket(self) -> IncomeBracket:
        half, seen = self.taxpayers / 2, 0
        for b in self.brackets:
            seen += b.taxpayers
            if seen >= half:
                return b
        raise ParseError("brackets don't reach half of all taxpayers")


MAX_THIN_SPACE = 3.0  # pt: gap between thousands groups of one number (columns are ≥ 5 pt apart)


def merge_number_words(words: list[dict]) -> list[str]:
    """One printed line (pdfplumber words, left to right) → tokens, with "1" "945" "538"
    (thin spaces) merged into "1945538". Column gaps are much wider than thin spaces."""
    out: list[str] = []
    prev: dict | None = None
    for w in sorted(words, key=lambda w: w["x0"]):
        text = w["text"]
        if (
            prev is not None
            and re.fullmatch(r"\d{3}", text)
            and re.fullmatch(r"–?\d+", out[-1])
            and w["x0"] - prev["x1"] < MAX_THIN_SPACE
        ):
            out[-1] += text
        else:
            out.append(text)
        prev = w
    return out


def _lines(words: list[dict], tolerance: float = 2.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tolerance:
            lines[-1].append(w)
        else:
            lines.append([w])
    return lines


def income_report_from_words(words: list[dict], year: int) -> IncomeReport:
    """Table 1 ("Übersicht …") of the report: the total row and the income brackets.

    Each data row has 11 numbers: taxpayers (prev. year, year, %), total income in
    1,000 EUR (prev., year, %), tax (prev., year, %), tax rate (prev., year). Checks: the
    brackets must add up to the total (count exactly, income within rounding) and each
    row's change column must match its two values.
    """
    total: tuple[int, int] | None = None
    brackets: list[IncomeBracket] = []
    for line in _lines(words):
        tokens = merge_number_words(line)
        nums = [t for t in tokens if re.fullmatch(r"\d+(,\d+)?", t)]
        text = " ".join(tokens)
        if len(nums) < 11:
            continue
        vals = nums[-11:]
        taxpayers, income = int(vals[1]), int(vals[4])
        change = round(100 * int(vals[1]) / int(vals[0]))
        if abs(change - int(vals[2].split(",")[0])) > 1:
            raise ParseError(f"row {text!r}: change column {vals[2]} ≠ {change}")
        if text.startswith("betrag der Einkünfte") and total is None:
            total = (taxpayers, income)
            continue
        m = re.match(r"^(\d+)\s*–\s*(\d+)\s", text) or re.match(r"^(\d+)\s+und mehr", text)
        if m and total is not None:
            low = int(m.group(1))
            high = int(m.group(2)) if m.lastindex == 2 else None
            brackets.append(IncomeBracket(low, high, taxpayers, income))
    if total is None or not brackets:
        raise ParseError("income table: total row or brackets not found")
    if sum(b.taxpayers for b in brackets) != total[0]:
        raise ParseError("income table: brackets don't add up to the total taxpayers")
    if abs(sum(b.income_keur for b in brackets) - total[1]) > len(brackets):
        raise ParseError("income table: brackets don't add up to the total income")
    if brackets[0].low != 0 or brackets[-1].high is not None:
        raise ParseError("income table: brackets don't cover 0 to open end")
    return IncomeReport(year, total[0], total[1], brackets)


def read_income_report(path: Path) -> IncomeReport:
    import pdfplumber  # build-time dependency only

    with pdfplumber.open(path) as pdf:
        cover = pdf.pages[0].extract_text() or ""
        m = re.search(r"L IV 3\s*–\s*j\s*/\s*(\d{2})", cover)
        if not m:
            raise ParseError(f"{path.name}: not a Statistischer Bericht L IV 3")
        year = 2000 + int(m.group(1))
        errors = []
        for page in pdf.pages[:8]:  # the table of contents mentions table 1 too: try each
            text = page.extract_text() or ""
            if "Übersicht zu den" in text and "Gesamtbetrag" in text:
                try:
                    return income_report_from_words(page.extract_words(x_tolerance=1), year)
                except ParseError as exc:
                    errors.append(f"p. {page.page_number}: {exc}")
    raise ParseError(f"{path.name}: table 1 (Übersicht) not found ({'; '.join(errors)})")
