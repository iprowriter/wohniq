"""Offline place lookup: free-text work location → coordinates, with no network.

Used by the commute estimate (enrich/commute_estimate.py) when live transit data isn't
available. Two local sources:

  * VBB stops (`data/vbb/stops.csv`) — every public-transport stop in the Berlin area,
    extracted once from VBB's open GTFS data with `make demo-stops`. Not committed.
  * Kiez centres from data/kieze.py — always available, so "work in Kreuzberg" resolves
    even when the stops file hasn't been downloaded.

Matching, first hit wins: rail station (S/U) name → alias → Kiez name → any other
stop → close spelling (difflib). Names are normalized first: case, umlauts/ß,
"S+U"/"S"/"U" prefixes, "Bhf", bracketed suffixes like "(Berlin)" or "[Tram]".
"""

from __future__ import annotations

import csv
import difflib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from core.logging import get_logger
from data.kieze import KIEZE

logger = get_logger(__name__)

STOPS_CSV = Path(__file__).resolve().parents[1] / "data" / "vbb" / "stops.csv"
FUZZY_CUTOFF = 0.85

# Common ways people name places that don't match the official stop name.
# Values are normalized keys (see `normalize`), never coordinates.
ALIASES = {
    "alex": "alexanderplatz",
    "hbf": "hauptbahnhof",
    "berlin hbf": "hauptbahnhof",
    "central station": "hauptbahnhof",
    "main station": "hauptbahnhof",
    "zoo": "zoologischer garten",
    "bahnhof zoo": "zoologischer garten",
    "ber": "flughafen ber",
    "airport": "flughafen ber",
    "ber airport": "flughafen ber",
}

_RAIL_PREFIX = re.compile(r"^(s\+u|s|u)\s+")
_BRACKETS = re.compile(r"\(.*?\)|\[.*?\]")


@dataclass(frozen=True)
class Place:
    name: str
    lat: float
    lng: float
    source: str  # "vbb" | "kiez"


def normalize(text: str) -> str:
    t = _BRACKETS.sub(" ", text.lower()).replace("ß", "ss")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    t = _RAIL_PREFIX.sub("", t.strip())
    t = re.sub(r"\b(bhf|bahnhof)\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    t = re.sub(r"strasse\b", "str", t)  # VBB abbreviates: "Friedrichstr." == "Friedrichstraße"
    t = re.sub(r"^berlin\s+|\s+berlin$", "", t)  # "Berlin Hauptbahnhof" → "hauptbahnhof"
    return t


def _is_rail_station(raw_name: str, location_type: str) -> bool:
    return location_type == "1" or bool(_RAIL_PREFIX.match(raw_name.lower().strip()))


class PlaceIndex:
    def __init__(self, stop_rows: list[dict] | None = None) -> None:
        self.rail: dict[str, Place] = {}
        self.other: dict[str, Place] = {}
        for row in stop_rows or []:
            key = normalize(row["name"])
            if not key:
                continue
            place = Place(row["name"], float(row["lat"]), float(row["lng"]), "vbb")
            bucket = (
                self.rail
                if _is_rail_station(row["name"], row.get("location_type", ""))
                else self.other
            )
            bucket.setdefault(key, place)  # first occurrence wins (stable)
        self.kiez = {normalize(k.name): Place(k.name, k.lat, k.lng, "kiez") for k in KIEZE}
        self._all_keys = list({**self.other, **self.kiez, **self.rail})

    @property
    def has_stops(self) -> bool:
        return bool(self.rail or self.other)

    def _exact(self, key: str) -> Place | None:
        for table in (self.rail, self.kiez, self.other):
            if key in table:
                return table[key]
        return None

    def resolve(self, text: str | None) -> Place | None:
        if not text:
            return None
        key = normalize(text)
        if not key:
            return None
        place = self._exact(key) or self._exact(ALIASES.get(key, ""))
        if place is not None:
            return place
        close = difflib.get_close_matches(key, self._all_keys, n=1, cutoff=FUZZY_CUTOFF)
        return self._exact(close[0]) if close else None


def load_stop_rows(path: Path = STOPS_CSV) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def get_place_index() -> PlaceIndex:
    rows = load_stop_rows()
    if not rows:
        logger.info(
            "VBB stops not found at %s — offline commute estimates only resolve Kiez names. "
            "Run `make demo-stops` once while online.",
            STOPS_CSV,
        )
    return PlaceIndex(rows)


@lru_cache(maxsize=256)
def resolve_place(text: str) -> Place | None:
    """Cached lookup against the default index (fuzzy matching isn't free)."""
    return get_place_index().resolve(text)
