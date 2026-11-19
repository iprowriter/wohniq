"""Berlin area gazetteer + area mention extraction (pure, stdlib only).

Why this exists: SearchCriteria used to have no area field, so "a quiet flat in Mitte,
Spandau, Lichtenberg, Treptow" was parsed as just "quiet" and the districts were thrown
away — users got flats from the other side of the city. This module is the single
source of truth for *which* place names we understand and *what listings they cover*.

Three layers of names:
  * Bezirke (12 districts). Compound ones ("Friedrichshain-Kreuzberg",
    "Treptow-Köpenick", …) cover the whole district.
  * Ortsteile (all 96 localities) — what Berliners mean in conversation. A name that is
    both a Bezirk and an Ortsteil ("Mitte", "Pankow", "Neukölln", "Spandau",
    "Lichtenberg", "Reinickendorf") resolves to the *Ortsteil*: "a flat in Mitte" means
    central Mitte, not Wedding. "Bezirk Mitte" / "Mitte district" selects the district.
  * Kiez names and nicknames ("Kollwitzkiez", "Reuterkiez", "P'berg", "Xberg", "SO36",
    "Kreuzkölln", "Fhain", "Nkln", …) that map onto the above.

Matching is forgiving about how people type: case, umlauts (ö / oe / o), ß/ss,
hyphens and apostrophes ("P-Berg", "P'berg", "Pberg"), missing spaces
("Prenzlauerberg") and small typos in longer names ("Kreutzberg").

Each mention is classified by its context:
  * "want"  — where the user wants to live (filter to these),
  * "avoid" — "not Neukölln", "anywhere but Marzahn" (exclude these),
  * "work"  — "I work in Mitte" (a commute target, not a living area).
List continuations inherit the context: in "not Neukölln or Wedding" both are avoided.

Coordinates are approximate Ortsteil centres (±~1 km); they're only used to find and
order *nearby* listings when nothing is available in the requested areas.
"""

from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass, field

# Only Bezirk-level areas have kind "district"; everything else is a "locality".
DISTRICT = "district"
LOCALITY = "locality"

# Beyond this distance from a requested area's centre a listing isn't "nearby".
NEARBY_MAX_KM = 6.0


@dataclass(frozen=True)
class Area:
    name: str  # canonical display name, e.g. "Prenzlauer Berg"
    district: str  # Bezirk it belongs to
    lat: float
    lng: float
    kind: str = LOCALITY
    aliases: tuple[str, ...] = ()
    # Listing Kiez names this area covers (listing.kiez values). Defaults to (name,).
    kieze: tuple[str, ...] = ()
    # Aliases that are also ordinary words ("wedding") need a place-like context.
    ambiguous: tuple[str, ...] = ()

    @property
    def covered_kieze(self) -> tuple[str, ...]:
        return self.kieze or (self.name,)


def _loc(name, district, lat, lng, *aliases, kieze=(), ambiguous=()) -> Area:
    return Area(name, district, lat, lng, LOCALITY, tuple(aliases), tuple(kieze), tuple(ambiguous))


def _bezirk(district, lat, lng, *aliases, name=None) -> Area:
    # Districts that share their name with an Ortsteil get a distinct canonical name
    # ("Bezirk Mitte"), so the bare word keeps meaning the Ortsteil.
    return Area(name or district, district, lat, lng, DISTRICT, tuple(aliases))


_MI, _FK, _PA, _CW = "Mitte", "Friedrichshain-Kreuzberg", "Pankow", "Charlottenburg-Wilmersdorf"
_SP, _SZ, _TS, _NK = "Spandau", "Steglitz-Zehlendorf", "Tempelhof-Schöneberg", "Neukölln"
_TK, _MH, _LI, _RE = "Treptow-Köpenick", "Marzahn-Hellersdorf", "Lichtenberg", "Reinickendorf"

AREAS: tuple[Area, ...] = (
    # --- Bezirke (whole districts) --------------------------------------------------
    _bezirk(
        _MI,
        52.531,
        13.370,
        "mitte district",
        "district mitte",
        "district of mitte",
        name="Bezirk Mitte",
    ),
    _bezirk(_FK, 52.505, 13.430, "xhain", "friedrichshain kreuzberg", "kreuzberg friedrichshain"),
    _bezirk(_PA, 52.590, 13.430, "pankow district", "district pankow", name="Bezirk Pankow"),
    _bezirk(_CW, 52.500, 13.285, "charlottenburg wilmersdorf"),
    _bezirk(_SP, 52.535, 13.185, "spandau district", name="Bezirk Spandau"),
    _bezirk(_SZ, 52.435, 13.245, "steglitz zehlendorf"),
    _bezirk(_TS, 52.440, 13.385, "tempelhof schoneberg", "tempelhof schoeneberg"),
    _bezirk(_NK, 52.445, 13.455, "neukolln district", name="Bezirk Neukölln"),
    _bezirk(_TK, 52.440, 13.580, "treptow kopenick", "treptow koepenick"),
    _bezirk(_MH, 52.525, 13.585, "marzahn hellersdorf"),
    _bezirk(_LI, 52.540, 13.500, "lichtenberg district", name="Bezirk Lichtenberg"),
    _bezirk(_RE, 52.600, 13.290, "reinickendorf district", name="Bezirk Reinickendorf"),
    # --- Mitte --------------------------------------------------------------------
    _loc(
        "Mitte",
        _MI,
        52.522,
        13.404,
        "berlin mitte",
        "berlin-mitte",
        "mitte berlin",
        "spandauer vorstadt",
        "scheunenviertel",
        "rosenthaler vorstadt",
        "fischerinsel",
    ),
    _loc("Moabit", _MI, 52.530, 13.342, "beusselkiez", "westfalischer viertel"),
    _loc("Hansaviertel", _MI, 52.519, 13.342),
    _loc("Tiergarten", _MI, 52.510, 13.357),
    _loc(
        "Wedding",
        _MI,
        52.550,
        13.360,
        "sprengelkiez",
        "brusseler kiez",
        "afrikanisches viertel",
        "leopoldplatz",
        ambiguous=("wedding",),
    ),
    _loc("Gesundbrunnen", _MI, 52.551, 13.390, "soldiner kiez", "brunnenviertel"),
    # --- Friedrichshain-Kreuzberg -------------------------------------------------
    _loc(
        "Friedrichshain",
        _FK,
        52.515,
        13.454,
        "fhain",
        "f hain",
        "friedrichhain",
        "boxhagener kiez",
        "boxi",
        "samariterkiez",
        "simon dach kiez",
        "traveplatz",
    ),
    _loc(
        "Kreuzberg",
        _FK,
        52.498,
        13.403,
        "xberg",
        "x berg",
        "kreuzberg 36",
        "kreuzberg 61",
        "so36",
        "so 36",
        "bergmannkiez",
        "graefekiez",
        "wrangelkiez",
        "chamissokiez",
        "kottbusser tor",
        "kotti",
    ),
    # --- Pankow -------------------------------------------------------------------
    _loc(
        "Prenzlauer Berg",
        _PA,
        52.539,
        13.424,
        "prenzlberg",
        "prenzl berg",
        "pberg",
        "p berg",
        "prenzlauer",
        "kollwitzkiez",
        "helmholtzkiez",
        "botzowviertel",
        "winsviertel",
        "gleimviertel",
        "komponistenviertel",
    ),
    _loc("Pankow", _PA, 52.569, 13.402, "alt pankow"),
    _loc("Weißensee", _PA, 52.556, 13.466, "weissensee", "weisensee"),
    _loc("Niederschönhausen", _PA, 52.582, 13.382),
    _loc("Heinersdorf", _PA, 52.573, 13.438),
    _loc("Blankenburg", _PA, 52.592, 13.447),
    _loc("Karow", _PA, 52.615, 13.480),
    _loc("Buch", _PA, 52.636, 13.492, ambiguous=("buch",)),
    _loc("Französisch Buchholz", _PA, 52.604, 13.430),
    _loc("Blankenfelde", _PA, 52.617, 13.392),
    _loc("Rosenthal", _PA, 52.598, 13.378),
    _loc("Wilhelmsruh", _PA, 52.588, 13.367),
    _loc("Stadtrandsiedlung Malchow", _PA, 52.578, 13.485),
    # --- Charlottenburg-Wilmersdorf -----------------------------------------------
    _loc("Charlottenburg", _CW, 52.510, 13.305, "klausenerplatz", "savignyplatz"),
    _loc("Wilmersdorf", _CW, 52.487, 13.317),
    _loc("Westend", _CW, 52.517, 13.264),
    _loc("Charlottenburg-Nord", _CW, 52.533, 13.297),
    _loc("Halensee", _CW, 52.496, 13.293),
    _loc("Schmargendorf", _CW, 52.477, 13.289),
    _loc("Grunewald", _CW, 52.484, 13.262),
    # --- Spandau ------------------------------------------------------------------
    _loc("Spandau", _SP, 52.536, 13.201, "spandau altstadt", "altstadt spandau"),
    _loc("Haselhorst", _SP, 52.542, 13.235),
    _loc("Siemensstadt", _SP, 52.540, 13.265),
    _loc("Staaken", _SP, 52.535, 13.145),
    _loc("Gatow", _SP, 52.486, 13.183),
    _loc("Kladow", _SP, 52.456, 13.144),
    _loc("Hakenfelde", _SP, 52.560, 13.205),
    _loc("Falkenhagener Feld", _SP, 52.552, 13.170),
    _loc("Wilhelmstadt", _SP, 52.518, 13.190),
    # --- Steglitz-Zehlendorf ------------------------------------------------------
    _loc("Steglitz", _SZ, 52.456, 13.322),
    _loc("Lichterfelde", _SZ, 52.430, 13.310),
    _loc("Lankwitz", _SZ, 52.435, 13.345),
    _loc("Zehlendorf", _SZ, 52.434, 13.255),
    _loc("Dahlem", _SZ, 52.458, 13.288),
    _loc("Nikolassee", _SZ, 52.430, 13.200),
    _loc("Wannsee", _SZ, 52.420, 13.165),
    # --- Tempelhof-Schöneberg -----------------------------------------------------
    _loc(
        "Schöneberg",
        _TS,
        52.483,
        13.353,
        "schoneberg",
        "akazienkiez",
        "rote insel",
        "nollendorfkiez",
        "bayerisches viertel",
    ),
    _loc("Friedenau", _TS, 52.470, 13.330),
    _loc("Tempelhof", _TS, 52.465, 13.385),
    _loc("Mariendorf", _TS, 52.437, 13.387),
    _loc("Marienfelde", _TS, 52.418, 13.367),
    _loc("Lichtenrade", _TS, 52.393, 13.405),
    # --- Neukölln -----------------------------------------------------------------
    _loc(
        "Neukölln",
        _NK,
        52.481,
        13.435,
        "nkln",
        "neukolle",
        "nord neukolln",
        "nordneukolln",
        "reuterkiez",
        "schillerkiez",
        "rixdorf",
        "weserkiez",
        "donaukiez",
        "kornerkiez",
        "flughafenkiez",
        "richardkiez",
    ),
    # The Kreuzberg/Neukölln border Kiez: people searching it accept either side.
    _loc("Kreuzkölln", _NK, 52.492, 13.425, "kreuzkolln", kieze=("Neukölln", "Kreuzberg")),
    _loc("Britz", _NK, 52.445, 13.435),
    _loc("Buckow", _NK, 52.420, 13.440),
    _loc("Rudow", _NK, 52.418, 13.495),
    _loc("Gropiusstadt", _NK, 52.425, 13.462),
    # --- Treptow-Köpenick ---------------------------------------------------------
    # Listing Kiez "Treptow" is Alt-Treptow; plain "Treptow" means the same here.
    _loc("Treptow", _TK, 52.490, 13.463, "alt treptow", "treptower park"),
    _loc("Plänterwald", _TK, 52.480, 13.475, "planterwald"),
    _loc("Baumschulenweg", _TK, 52.465, 13.487),
    _loc("Johannisthal", _TK, 52.445, 13.505),
    _loc("Niederschöneweide", _TK, 52.455, 13.515),
    _loc("Oberschöneweide", _TK, 52.463, 13.522, "schoneweide", "schoeneweide"),
    _loc("Adlershof", _TK, 52.435, 13.545),
    _loc("Altglienicke", _TK, 52.410, 13.545),
    _loc("Bohnsdorf", _TK, 52.395, 13.565),
    _loc("Köpenick", _TK, 52.445, 13.575, "kopenick", "altstadt kopenick"),
    _loc("Friedrichshagen", _TK, 52.450, 13.625),
    _loc("Rahnsdorf", _TK, 52.440, 13.690),
    _loc("Grünau", _TK, 52.415, 13.580),
    _loc("Müggelheim", _TK, 52.410, 13.665),
    _loc("Schmöckwitz", _TK, 52.375, 13.645),
    # --- Marzahn-Hellersdorf ------------------------------------------------------
    _loc("Marzahn", _MH, 52.545, 13.545),
    _loc("Hellersdorf", _MH, 52.535, 13.605),
    _loc("Biesdorf", _MH, 52.510, 13.555),
    _loc("Kaulsdorf", _MH, 52.510, 13.590),
    _loc("Mahlsdorf", _MH, 52.505, 13.615),
    # --- Lichtenberg --------------------------------------------------------------
    _loc("Lichtenberg", _LI, 52.515, 13.495, "alt lichtenberg", "weitlingkiez", "kaskelkiez"),
    _loc("Friedrichsfelde", _LI, 52.505, 13.510),
    _loc("Karlshorst", _LI, 52.482, 13.527),
    _loc("Rummelsburg", _LI, 52.497, 13.495, "rummelsburger bucht"),
    _loc("Fennpfuhl", _LI, 52.528, 13.475),
    _loc("Alt-Hohenschönhausen", _LI, 52.545, 13.500),
    _loc("Neu-Hohenschönhausen", _LI, 52.565, 13.510, "hohenschonhausen", "hohenschoenhausen"),
    _loc("Falkenberg", _LI, 52.570, 13.545),
    _loc("Malchow", _LI, 52.582, 13.475),
    _loc("Wartenberg", _LI, 52.574, 13.518),
    # --- Reinickendorf ------------------------------------------------------------
    _loc("Reinickendorf", _RE, 52.575, 13.335),
    _loc("Tegel", _RE, 52.585, 13.285),
    _loc("Wittenau", _RE, 52.590, 13.325),
    _loc("Märkisches Viertel", _RE, 52.600, 13.355, "markisches viertel"),
    _loc("Borsigwalde", _RE, 52.580, 13.305),
    _loc("Waidmannslust", _RE, 52.605, 13.315),
    _loc("Hermsdorf", _RE, 52.618, 13.305),
    _loc("Frohnau", _RE, 52.632, 13.290),
    _loc("Lübars", _RE, 52.617, 13.355),
    _loc("Heiligensee", _RE, 52.615, 13.225),
    _loc("Konradshöhe", _RE, 52.590, 13.225),
)

BY_NAME: dict[str, Area] = {a.name: a for a in AREAS}

# --- Normalisation ----------------------------------------------------------------

_FOLD = str.maketrans(
    {
        "ä": "a",
        "ö": "o",
        "ü": "u",
        "ß": "ss",
        "é": "e",
        "’": " ",
        "'": " ",
        "`": " ",
        "-": " ",
        "_": " ",
        "/": " / ",
    }
)
_SPACES = re.compile(r"[ \t]+")


def normalize(text: str) -> str:
    """Lowercase and fold umlauts/punctuation so "P'berg", "P-Berg" → "p berg"."""
    return _SPACES.sub(" ", text.lower().translate(_FOLD)).strip()


def _umlaut_ascii(text: str) -> str:
    """German ASCII transliteration: ö → oe (people type "Neukoelln")."""
    return text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")


def _alias_forms(area: Area) -> set[str]:
    forms: set[str] = set()
    for raw in (area.name, *area.aliases):
        for variant in (raw, _umlaut_ascii(raw)):
            norm = normalize(variant)
            forms.add(norm)
            if " " in norm:
                forms.add(norm.replace(" ", ""))  # "prenzlauerberg", "friedrichshainkreuzberg"
    return forms


def _build_index() -> dict[str, Area]:
    index: dict[str, Area] = {}
    for area in AREAS:
        for form in _alias_forms(area):
            if form in index and index[form] is not area:
                raise ValueError(f"alias {form!r} is used by {index[form].name} and {area.name}")
            index[form] = area
    return index


ALIAS_INDEX: dict[str, Area] = _build_index()
# Longest first, so "friedrichshain kreuzberg" wins over "friedrichshain".
_ALIASES_BY_LENGTH = sorted(ALIAS_INDEX, key=len, reverse=True)
_AMBIGUOUS = {normalize(w) for a in AREAS for w in a.ambiguous}
_ALIAS_PATTERN = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(a) for a in _ALIASES_BY_LENGTH) + r")(?![a-z0-9])"
)
# Single-word names long enough for safe typo matching ("kreutzberg", "lichtenburg").
_FUZZY_TARGETS = sorted(
    {a for a in ALIAS_INDEX if " " not in a and len(a) >= 7 and a not in _AMBIGUOUS}
)
_FUZZY_CUTOFF = 0.88


def resolve_area(name: str | None) -> Area | None:
    """Canonical Area for a place name / alias / nickname, or None if not a Berlin area."""
    if not name:
        return None
    norm = normalize(name)
    for prefix in ("berlin ", "in "):
        if norm.startswith(prefix) and norm[len(prefix) :] in ALIAS_INDEX:
            norm = norm[len(prefix) :]
    if norm in ALIAS_INDEX:
        return ALIAS_INDEX[norm]
    compact = norm.replace(" ", "")
    if compact in ALIAS_INDEX:
        return ALIAS_INDEX[compact]
    if " " not in norm and len(norm) >= 7:
        close = difflib.get_close_matches(norm, _FUZZY_TARGETS, n=1, cutoff=_FUZZY_CUTOFF)
        if close:
            return ALIAS_INDEX[close[0]]
    return None


def canonical_areas(names: list[str] | tuple[str, ...]) -> list[str]:
    """Canonical, de-duplicated area names (order kept); unknown names are dropped."""
    out: list[str] = []
    for name in names:
        area = resolve_area(str(name))
        if area is not None and area.name not in out:
            out.append(area.name)
    return out


# --- Mentions in free text ------------------------------------------------------------

WANT, AVOID, WORK = "want", "avoid", "work"

# Negation directly before the place ("not Neukölln", "anywhere but Marzahn",
# "don't want to live in Wedding", "except for Mitte"). Deliberately adjacent-only so
# "not too loud in Mitte" is still a wish for Mitte.
_AVOID_BEFORE = re.compile(
    r"(?:\b(?:not|no|except(?: for)?|excluding|exclude|avoid|avoiding|outside(?: of)?|"
    r"other than|rather than|instead of|apart from|anywhere but|anything but|everywhere but|"
    r"but not|nicht|ausser|kein|keine|never)"
    r"|\bdon t (?:want|like)|\bdo not (?:want|like)|\bhate)"
    r"(?: (?:to live|live|living|to be|be|being))?(?: (?:in|near|around|the|of|im))? ?$"
)
_AVOID_AFTER = re.compile(r"^ ?(?:is|are)? ?(?:a )?(?:no go|nogo|too (?:loud|expensive|far))")
# A work (or study) word within three words of the place: "I work in Mitte", "my office
# is in Kreuzberg", "internship at Zalando in Friedrichshain" — but not "I work from home
# and want a flat in Mitte".
_WORK_BEFORE = re.compile(
    r"\b(?:work|works|working|worked|office|job|workplace|employer|arbeite|arbeit|buro|"
    r"commute to|commuting to|study|studying|university|uni|campus|college|phd|lecturer|"
    r"teacher|intern|internship|apprenticeship|ausbildung|trainee|traineeship)\b"
    r"(?: [^ ]+){0,3} ?$"
)
# Teaching reaches one word further: "I teach at a school in Neukölln". ("school" alone is
# NOT a workplace word: "near a good school in Pankow" is a family choosing where to live.)
_TEACH_BEFORE = re.compile(r"\b(?:teach|teaches|teaching)\b(?: [^ ]+){0,4} ?$")
# "student" only as "a student at/in ...": a "student room in Mitte" is a place to live.
_STUDENT_BEFORE = re.compile(r"\bstudents? (?:at|in)\b(?: [^ ]+){0,3} ?$")
# Words that make an ambiguous alias ("wedding") read as a place.
_PLACE_BEFORE = re.compile(r"\b(?:in|near|around|nahe|im|to|from|or|and|,)\s*$")
# Separators that continue a list: "Mitte, Spandau or Lichtenberg".
_LIST_GAP = re.compile(r"^(?:\s|,|;|/|&|\band\b|\bor\b|\bund\b|\boder\b|\bnor\b|\bin\b)*$")
# " but " is not a break: "anywhere but Neukölln" must keep its negation.
_CLAUSE_BREAK = re.compile(r"[.;!?\n]|,(?! ?(?:or|and)\b)| while | because | whereas ")


@dataclass(frozen=True)
class AreaMention:
    area: Area
    role: str  # WANT | AVOID | WORK
    start: int
    end: int
    text: str


@dataclass
class AreaAnalysis:
    want: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    work: list[str] = field(default_factory=list)
    mentions: list[AreaMention] = field(default_factory=list)


def _clause_before(norm: str, start: int, floor: int) -> str:
    """Text from the last clause break (or the previous mention) up to `start`."""
    window = norm[floor:start]
    breaks = list(_CLAUSE_BREAK.finditer(window))
    return window[breaks[-1].end() :] if breaks else window


def _original_is_capitalised(original: str, alias: str) -> bool:
    return re.search(r"\b" + re.escape(alias.capitalize()) + r"\b", original) is not None


def _raw_matches(original: str, norm: str) -> list[tuple[int, int, str, Area]]:
    found: list[tuple[int, int, str, Area]] = []
    taken: list[tuple[int, int]] = []
    for m in _ALIAS_PATTERN.finditer(norm):
        alias = m.group(1)
        if alias in _AMBIGUOUS:
            before = norm[max(0, m.start() - 12) : m.start()]
            if not (_original_is_capitalised(original, alias) or _PLACE_BEFORE.search(before)):
                continue  # "after our wedding" is not the Wedding in Mitte
        found.append((m.start(), m.end(), alias, ALIAS_INDEX[alias]))
        taken.append((m.start(), m.end()))
    # Typo-tolerant pass over remaining long words ("Kreutzberg", "Lichtenburg").
    for m in re.finditer(r"[a-z]{7,}", norm):
        if any(s <= m.start() < e for s, e in taken) or m.group(0) in ALIAS_INDEX:
            continue
        close = difflib.get_close_matches(m.group(0), _FUZZY_TARGETS, n=1, cutoff=_FUZZY_CUTOFF)
        if close:
            found.append((m.start(), m.end(), m.group(0), ALIAS_INDEX[close[0]]))
    return sorted(found, key=lambda x: x[0])


def find_area_mentions(text: str) -> AreaAnalysis:
    """Find every Berlin area named in `text` and whether it's wanted, avoided or work."""
    norm = normalize(text)
    analysis = AreaAnalysis()
    prev_end = 0
    prev_role: str | None = None
    for start, end, alias, area in _raw_matches(text, norm):
        gap = norm[prev_end:start]
        if prev_role is not None and _LIST_GAP.match(gap):
            role = prev_role  # list continuation keeps the context
        else:
            before = _clause_before(norm, start, prev_end if prev_role is not None else 0)
            after = norm[end : end + 24]
            if _AVOID_BEFORE.search(before) or _AVOID_AFTER.match(after):
                role = AVOID
            elif any(p.search(before) for p in (_WORK_BEFORE, _TEACH_BEFORE, _STUDENT_BEFORE)):
                role = WORK
            else:
                role = WANT
        analysis.mentions.append(AreaMention(area, role, start, end, alias))
        bucket = {WANT: analysis.want, AVOID: analysis.avoid, WORK: analysis.work}[role]
        if area.name not in bucket:
            bucket.append(area.name)
        prev_end, prev_role = end, role
    return analysis


# --- Listing ↔ area matching ------------------------------------------------------------


def _norm_key(name: str | None) -> str:
    return normalize(name or "")


def listing_in_area(kiez: str | None, district: str | None, area: Area) -> bool:
    """True if a listing (by its Kiez and Bezirk) lies in `area`."""
    if area.kind == DISTRICT:
        return _norm_key(district) == _norm_key(area.district)
    listing_area = resolve_area(kiez) if kiez else None
    covered = {_norm_key(k) for k in area.covered_kieze}
    if _norm_key(kiez) in covered:
        return True
    return listing_area is not None and _norm_key(listing_area.name) in covered


def matching_area(kiez: str | None, district: str | None, names: list[str]) -> str | None:
    """The first of `names` (canonical area names) the listing lies in, else None."""
    for name in names:
        area = BY_NAME.get(name)
        if area is not None and listing_in_area(kiez, district, area):
            return name
    return None


def area_sql_terms(names: list[str]) -> tuple[list[str], list[str]]:
    """(kiez values, district values) a SQL filter should match for these areas."""
    kieze: list[str] = []
    districts: list[str] = []
    for name in names:
        area = BY_NAME.get(name)
        if area is None:
            continue
        if area.kind == DISTRICT:
            districts.append(area.district)
        else:
            kieze.extend(k for k in area.covered_kieze if k not in kieze)
    return kieze, districts


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_area(lat: float, lng: float, names: list[str]) -> tuple[str, float] | None:
    """(closest requested area, km from its centre) for a listing location."""
    best: tuple[str, float] | None = None
    for name in names:
        area = BY_NAME.get(name)
        if area is None:
            continue
        d = haversine_km(lat, lng, area.lat, area.lng)
        if best is None or d < best[1]:
            best = (name, d)
    return best


def describe_areas(names: list[str], *, conj: str = "or") -> str:
    """ "Mitte", "Mitte or Spandau", "Mitte, Spandau or Treptow"."""
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} {conj} {names[-1]}"
