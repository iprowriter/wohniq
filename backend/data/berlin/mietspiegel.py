"""Read the Berliner Mietspiegel 2026: the table (189 rows) and the feature checklist.

Both parsers are strict: if the PDF doesn't yield exactly the structure the brochure
describes (every row 1–189 once, contiguous size bands, 5 groups on both sides), they raise
`ParseError` rather than ship a partial table.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

LOCATIONS = ("simple", "medium", "good")  # einfache / mittlere / gute Wohnlage
# Rows 1–67 simple, 68–129 medium, 130–189 good (Mietspiegeltabelle 2026).
_LOCATION_ROWS = {"simple": (1, 67), "medium": (68, 129), "good": (130, 189)}

# Building-age bands (Bezugsfertigkeit) in table order. `east`/`west` = only for addresses
# in the former East/West (Wohnlagenverzeichnis "stadtteil"); None = both.
PERIODS: dict[str, dict] = {
    "pre1918": {"label": "before 1918", "from": None, "to": 1918, "side": None},
    "1919-1949": {"label": "1919–1949", "from": 1919, "to": 1949, "side": None},
    "1950-1964": {"label": "1950–1964", "from": 1950, "to": 1964, "side": None},
    "1965-1972": {"label": "1965–1972", "from": 1965, "to": 1972, "side": None},
    "1973-1985-west": {"label": "1973–1985 (West)", "from": 1973, "to": 1985, "side": "west"},
    "1986-1990-west": {"label": "1986–1990 (West)", "from": 1986, "to": 1990, "side": "west"},
    "1973-1990-east": {"label": "1973–1990 (East)", "from": 1973, "to": 1990, "side": "east"},
    "1991-2001": {"label": "1991–2001", "from": 1991, "to": 2001, "side": None},
    "2002-2009": {"label": "2002–2009", "from": 2002, "to": 2009, "side": None},
    "2010-2015": {"label": "2010–2015", "from": 2010, "to": 2015, "side": None},
    "2016-2019": {"label": "2016–2019", "from": 2016, "to": 2019, "side": None},
    "2020-2024": {"label": "2020–2024", "from": 2020, "to": 2024, "side": None},
}

_PERIOD_TEXT = {
    "bis 1918": "pre1918",
    "1919 bis 1949": "1919-1949",
    "1950 bis 1964": "1950-1964",
    "1965 bis 1972": "1965-1972",
    "1973 bis 1985 West": "1973-1985-west",
    "1986 bis 1990 West": "1986-1990-west",
    "1973 bis 1990 Ost*": "1973-1990-east",
    "1991 bis 2001**": "1991-2001",
    "2002 bis 2009": "2002-2009",
    "2010 bis 2015": "2010-2015",
    "2016 bis 2019": "2016-2019",
    "2020 bis 2024": "2020-2024",
}

_PRICE = r"(\d{1,2},\d{2}) €"
_ROW = re.compile(
    r"(?<!\S)(?P<row>\d{1,3}) "
    r"(?:(?P<period>[Bb]is 1918|\d{4} bis \d{4}(?: West| Ost\*)?(?:\*\*)?) )?"
    r"(?P<size>bis unter \d+ m²|\d+ m² bis unter \d+ m²|ab \d+ m²|alle Wohnflächen) "
    + _PRICE
    + " "
    + _PRICE
    + " "
    + _PRICE
)


class ParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class RentRow:
    row: int
    location: str
    period: str
    size_min: int  # m², inclusive
    size_max: int | None  # m², exclusive; None = no upper bound
    low: float  # €/m² net cold, lower end of the range
    mean: float
    high: float

    def to_dict(self) -> dict:
        return asdict(self)


def _de(value: str) -> float:
    return float(value.replace(",", "."))


def _size_band(text: str) -> tuple[int, int | None]:
    if text == "alle Wohnflächen":
        return 0, None
    nums = [int(n) for n in re.findall(r"\d+", text)]
    if text.startswith("bis unter"):
        return 0, nums[0]
    if text.startswith("ab"):
        return nums[0], None
    return nums[0], nums[1]


def _location_for(row: int) -> str:
    for loc, (lo, hi) in _LOCATION_ROWS.items():
        if lo <= row <= hi:
            return loc
    raise ParseError(f"row {row} is outside 1–189")


def parse_rent_table_text(text: str) -> list[RentRow]:
    """Rows from the table PDF's text (the three location tables are interleaved)."""
    flat = re.sub(r"\s+", " ", text)
    found: dict[int, RentRow] = {}
    for m in _ROW.finditer(flat):
        n = int(m["row"])
        if not 1 <= n <= 189 or n in found:
            continue
        period = m["period"]
        lo, mean, hi = _de(m[4]), _de(m[5]), _de(m[6])
        size_min, size_max = _size_band(m["size"])
        found[n] = RentRow(
            n,
            _location_for(n),
            _PERIOD_TEXT[period[0].lower() + period[1:]] if period else "",
            size_min,
            size_max,
            lo,
            mean,
            hi,
        )
    missing = sorted(set(range(1, 190)) - set(found))
    if missing:
        raise ParseError(f"Mietspiegel table: rows not found: {missing}")

    # A row without a building age continues the previous row's (within its table).
    rows: list[RentRow] = []
    current = ""
    for n in range(1, 190):
        r = found[n]
        if n in (lo for lo, _ in _LOCATION_ROWS.values()) and not r.period:
            raise ParseError(f"row {n} starts a table but has no building age")
        current = r.period or current
        rows.append(RentRow(**{**r.to_dict(), "period": current}))
    _validate(rows)
    return rows


def _validate(rows: list[RentRow]) -> None:
    for r in rows:
        if not r.low <= r.mean <= r.high:
            raise ParseError(f"row {r.row}: range {r.low}–{r.high} doesn't contain {r.mean}")
    for loc in LOCATIONS:
        periods_seen: list[str] = []
        for r in (r for r in rows if r.location == loc):
            if not periods_seen or periods_seen[-1] != r.period:
                periods_seen.append(r.period)
        if periods_seen != list(PERIODS):
            raise ParseError(f"{loc}: building ages {periods_seen} ≠ {list(PERIODS)}")
        for period in PERIODS:
            band = [r for r in rows if r.location == loc and r.period == period]
            edge = 0
            for r in band:
                if r.size_min != edge:
                    raise ParseError(f"row {r.row}: size band starts at {r.size_min}, not {edge}")
                edge = r.size_max if r.size_max is not None else -1
            if edge != -1:
                raise ParseError(f"{loc} {period}: last size band isn't open-ended")


def read_rent_table(path: Path) -> list[RentRow]:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return parse_rent_table_text(text)


# --- Orientierungshilfe (feature checklist) -------------------------------------------

GROUPS = {
    1: ("bath", "Bad/WC/Gäste-WC"),
    2: ("kitchen", "Küche"),
    3: ("flat", "Wohnung"),
    4: ("building", "Gebäude"),
    5: ("surroundings", "Wohnumfeld"),
}
# Pages (0-based) of No. 11 "Orientierungshilfe für die Spanneneinordnung".
CHECKLIST_PAGES = (23, 24, 25)
# Energy items: (sign, kWh/(m²a) threshold). "-": consumption greater than; "+": less than.
ENERGY_THRESHOLDS = {"-": (145, 195, 235), "+": (120, 100, 80)}
# Expected item counts per (group, sign), from the brochure; a mismatch stops the build.
EXPECTED_COUNTS = {
    (1, "-"): 10,
    (1, "+"): 11,
    (2, "-"): 7,
    (2, "+"): 7,
    (3, "-"): 8,
    (3, "+"): 11,
    (4, "-"): 11,
    (4, "+"): 11,
    (5, "-"): 3,
    (5, "+"): 4,
}

# Lines that end the current item. ("oder" only as a whole line: inside an item, wrapped
# lines often start with "oder …".)
_TERMINATOR_LINES = {"oder"}
_TERMINATORS = (
    "(End-)Energieverbrauchskennwert",
    "Fortsetzung",
    "BERLINER MIETSPIEGEL",
    "Wohnwertmindernde",
    "Wohnwerterhöhende",
    "11. Orientierungshilfe",
)


@dataclass(frozen=True)
class ChecklistItem:
    id: str  # e.g. "bath-minus-03", "building-plus-energy-100"
    group: int
    sign: str  # "-" lowers the value, "+" raises it
    text_de: str
    energy_kwh: int | None = None  # set for the six energy-consumption boxes

    def to_dict(self) -> dict:
        return asdict(self)


def _join_lines(lines: list[str]) -> str:
    out = ""
    for line in lines:
        line = line.strip()
        if not out:
            out = line
        elif out.endswith("-") and line[:1].islower():
            out = out[:-1] + line  # hyphenated line break ("Elekt-" + "roheizstrahler")
        elif out.endswith(("-", "/")):
            out += line
        else:
            out += " " + line
    return re.sub(r"\s+", " ", out).strip()


def parse_checklist_columns(columns: list[tuple[str, str]]) -> list[ChecklistItem]:
    """Items from (sign, column text) chunks in reading order."""
    items: dict[tuple[int, str], list[list[str]]] = {}
    group_by_sign: dict[str, int] = {}  # a column continues its group across pages/bands
    for sign, text in columns:
        group = group_by_sign.get(sign)
        current: list[str] | None = None
        for raw in text.splitlines():
            line = raw.strip()
            header = re.match(r"Merkmalgruppe (\d):", line)
            if header:
                group, current = int(header[1]), None
                group_by_sign[sign] = group
                continue
            if (
                not line
                or re.fullmatch(r"\d+", line)
                or line in _TERMINATOR_LINES
                or line.startswith(_TERMINATORS)
            ):
                current = None
                continue
            if line.startswith("☐"):
                if group is None:
                    raise ParseError(f"checklist box before any group: {line!r}")
                current = [line.lstrip("☐ ").strip()]
                items.setdefault((group, sign), []).append(current)
            elif current is not None:
                current.append(line)

    result: list[ChecklistItem] = []
    for (group, sign), raw_items in sorted(items.items()):
        key = GROUPS[group][0]
        word = "minus" if sign == "-" else "plus"
        n = 0
        for lines in raw_items:
            text = _join_lines(lines)
            kwh = re.match(r"(größer|kleiner) als (\d+) kWh", text)
            if kwh:
                value = int(kwh[2])
                result.append(
                    ChecklistItem(f"{key}-{word}-energy-{value}", group, sign, text, value)
                )
            else:
                n += 1
                result.append(ChecklistItem(f"{key}-{word}-{n:02d}", group, sign, text))
    _validate_checklist(result)
    return result


def _validate_checklist(items: list[ChecklistItem]) -> None:
    counts: dict[tuple[int, str], int] = {}
    for it in items:
        counts[(it.group, it.sign)] = counts.get((it.group, it.sign), 0) + 1
    if counts != EXPECTED_COUNTS:
        raise ParseError(f"checklist counts {counts} ≠ expected {EXPECTED_COUNTS}")
    for sign, values in ENERGY_THRESHOLDS.items():
        got = sorted(it.energy_kwh for it in items if it.sign == sign and it.energy_kwh)
        if got != sorted(values):
            raise ParseError(f"energy thresholds ({sign}) {got} ≠ {sorted(values)}")
    for it in items:
        if len(it.text_de) < 8 or "☐" in it.text_de:
            raise ParseError(f"suspicious checklist text: {it.text_de!r}")


def read_checklist(path: Path) -> list[ChecklistItem]:
    """Split each checklist page into its two columns (− left, + right) and parse them.

    On the last page the full-width notes under group 4 and the footnote under group 5 are
    cut away first, so they can't run into the column text.
    """
    import pdfplumber

    columns: list[tuple[str, str]] = []
    with pdfplumber.open(path) as pdf:
        for index in CHECKLIST_PAGES:
            page = pdf.pages[index]
            bands = [(0.0, float(page.height))]
            if index == CHECKLIST_PAGES[-1]:
                bands = _last_page_bands(page)
            for top, bottom in bands:
                for sign, x0, x1 in (("-", 0, page.width / 2), ("+", page.width / 2, page.width)):
                    columns.append((sign, page.crop((x0, top, x1, bottom)).extract_text() or ""))
    return parse_checklist_columns(columns)


def _last_page_bands(page) -> list[tuple[float, float]]:
    words = page.extract_words()
    notes_top = mg5_top = foot_top = None
    # The "oder" between the insulation item and the energy items is centred across both
    # columns; cut its line out so neither half ("od" / "der") joins an item.
    or_line = next(
        (
            w
            for w in words
            if w["text"] == "oder" and abs((w["x0"] + w["x1"]) / 2 - page.width / 2) < 40
        ),
        None,
    )
    for i, w in enumerate(words):
        nxt = words[i + 1]["text"] if i + 1 < len(words) else ""
        if w["text"] == "Die" and nxt.startswith("(End-)Energieverbrauchskennwerte"):
            notes_top = notes_top or w["top"]
        if w["text"] == "Merkmalgruppe" and nxt == "5:":
            mg5_top = mg5_top or w["top"]
        if w["text"] == "*" and nxt == "Hinweise":
            foot_top = foot_top or w["top"]
    if not (notes_top and mg5_top and foot_top and or_line):
        raise ParseError("checklist: couldn't locate the notes on the last page")
    return [
        (0.0, or_line["top"] - 1),
        (or_line["bottom"] + 1, notes_top - 1),
        (mg5_top - 1, foot_top - 1),
    ]
