"""Deterministic keyword extraction — the parser's fallback (pure, stdlib only).

When the LLM parse fails validation twice, we fall back to this rule-based extractor
so the app never crashes on a bad generation (SPEC F1 AC3). It's intentionally
modest — regex and keyword matching — and returns a plain dict that maps onto the
SearchCriteria fields. Kept stdlib-only so it's unit-testable without pydantic.
"""

from __future__ import annotations

import re

from search.areas import find_area_mentions, resolve_area

CANONICAL_AMENITIES = ("cafes", "parks", "supermarket", "nightlife", "gym")

_AMENITY_KEYWORDS = {
    "cafes": ["cafe", "café", "coffee"],
    "parks": ["park", "green space", "greenery"],
    "supermarket": ["supermarket", "grocery", "groceries"],
    "nightlife": ["nightlife", "bar", "club", "pub"],
    "gym": ["gym", "fitness"],
}
_QUIET_KEYWORDS = ["quiet", "calm", "peaceful", "not too loud", "residential", "tranquil"]
_TRANSPORT_KEYWORDS = [
    "transport", "u-bahn", "s-bahn", "ubahn", "sbahn", "commute",
    "well connected", "connected", "metro", "tram", "public transit",
]


_AMOUNT = r"(\d{1,2}(?:[.,]\d{1,3})?\s*k\b|\d[\d.,]*)"
_NOT_MONEY = r"(?!\s*(?:m²|m2|sqm|square|qm|rooms?|zimmer|zi\b|min))"
_RENT_PATTERNS = (
    r"€\s*" + _AMOUNT,
    _AMOUNT + r"\s*(?:€|eur\b|euros?\b)",
    r"budget[^\d]{0,12}" + _AMOUNT,
    # "under 1000", "max 1.2k", "up to 1400" — but not "under 60 m²"
    r"\b(?:under|below|max(?:imum)?|up to|less than|no more than|at most|bis)\s*" + _AMOUNT
    + _NOT_MONEY,
)


def _parse_amount(raw: str) -> int | None:
    """'1,500' / '1.500' → 1500; '1.5k' / '2k' → 1500 / 2000."""
    raw = raw.strip().lower().replace(" ", "")
    if raw.endswith("k"):
        try:
            return int(round(float(raw[:-1].replace(",", ".")) * 1000))
        except ValueError:
            return None
    digits = raw.rstrip(".,").replace(".", "").replace(",", "")
    return int(digits) if digits.isdigit() else None


def _extract_rent(text: str) -> int | None:
    for pattern in _RENT_PATTERNS:
        for m in re.finditer(pattern, text, re.I):
            amount = _parse_amount(m.group(1))
            # Plausible monthly rents only (skips "€5 coffee", "max 3 changes").
            if amount is not None and amount >= 100:
                return amount
    return None


def _extract_rooms(text: str) -> float | None:
    m = re.search(r"(\d(?:[.,]5)?)\s*-?\s*(?:rooms?|zimmer|zi\b)", text, re.I)
    return float(m.group(1).replace(",", ".")) if m else None


def _extract_size(text: str) -> int | None:
    m = re.search(r"(\d{2,3})\s*(?:m²|m2|sqm|square)", text, re.I)
    return int(m.group(1)) if m else None


def _extract_work_location(text: str) -> str | None:
    m = re.search(
        r"(?:work(?:ing)?\s+(?:in|near|at|by|close to)|office\s+(?:is\s+)?(?:in|at|near)|"
        r"commut(?:e|ing)\s+to|"
        r"near|close to|around)\s+"
        r"([A-ZÄÖÜ][\wäöüß'-]+(?:\s+[A-ZÄÖÜ][\wäöüß'-]+)?)",
        text,
    )
    return m.group(1).strip() if m else None


def workplace_or_none(work_location: str | None, work_areas: list[str]) -> str | None:
    """Keep a work location unless it's a Berlin area the text doesn't call a workplace.

    "quiet 2-room near Mitte" names where to live, not a workplace: a place that is a
    Berlin area only counts as work location when the text says so ("I work in Mitte",
    "my office is in ...", "commute to ..."); `work_areas` are those mentions. Landmarks
    that aren't areas ("Alexanderplatz") are always kept. The one rule for both parser
    paths: the keyword extractor and the LLM (search/parser.py `merge_areas`).
    """
    area = resolve_area(work_location) if work_location else None
    if area is not None and area.name not in work_areas:
        return None
    return work_location


def resolve_workplace(candidate: str | None, work_areas: list[str]) -> str | None:
    """The work location, from a candidate (parsed or the LLM's) and the text's workplace areas.

    1. Keep the candidate unless it's a Berlin area the text doesn't call a workplace
       (`workplace_or_none`).
    2. If nothing is left but the text names an area as the workplace ("I work in Mitte",
       "internship in Xberg"), use that area's proper name ("Mitte", "Kreuzberg").
    Only areas the text explicitly calls a workplace are added: a loose "near X" is not,
    so the LLM's judgement isn't overridden for places like "close to Görlitzer Park".
    The one rule for both parser paths (keyword extractor and LLM).
    """
    return workplace_or_none(candidate, work_areas) or (work_areas[0] if work_areas else None)


def extract_areas(text: str) -> tuple[list[str], list[str], list[str]]:
    """(areas to live in, areas to avoid, areas named as the workplace) from free text."""
    found = find_area_mentions(text)
    want = [a for a in found.want if a not in found.avoid]
    return want, found.avoid, found.work


def extract_criteria(text: str) -> dict:
    """Best-effort structured criteria from free text. Always returns every field."""
    low = text.lower()

    amenities = [
        canon
        for canon, words in _AMENITY_KEYWORDS.items()
        if any(w in low for w in words)
    ]

    furnished: bool | None = None
    if "unfurnished" in low:
        furnished = False
    elif "furnished" in low:
        furnished = True

    areas, excluded, work_areas = extract_areas(text)
    work_location = resolve_workplace(_extract_work_location(text), work_areas)

    return {
        "max_warm_rent": _extract_rent(text),
        "min_rooms": _extract_rooms(text),
        "min_size_m2": _extract_size(text),
        "work_location": work_location,
        "transport_priority": any(k in low for k in _TRANSPORT_KEYWORDS),
        "quiet_priority": any(k in low for k in _QUIET_KEYWORDS),
        "desired_amenities": amenities,
        "furnished": furnished,
        "areas": areas,
        "excluded_areas": excluded,
        "notes": text,  # never lose the original request in fallback mode
    }
