"""Deterministic keyword extraction — the parser's fallback (pure, stdlib only).

When the LLM parse fails validation twice, we fall back to this rule-based extractor
so the app never crashes on a bad generation (SPEC F1 AC3). It's intentionally
modest — regex and keyword matching — and returns a plain dict that maps onto the
SearchCriteria fields. Kept stdlib-only so it's unit-testable without pydantic.
"""

from __future__ import annotations

import re

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


def _extract_rent(text: str) -> int | None:
    for pattern in (r"€\s*([\d.,]+)", r"([\d.,]+)\s*€", r"([\d.,]+)\s*eur", r"budget[^\d]{0,12}([\d.,]+)"):
        m = re.search(pattern, text, re.I)
        if m:
            digits = m.group(1).replace(".", "").replace(",", "")
            if digits.isdigit():
                return int(digits)
    return None


def _extract_rooms(text: str) -> float | None:
    m = re.search(r"(\d(?:[.,]5)?)\s*-?\s*(?:rooms?|zimmer|zi\b)", text, re.I)
    return float(m.group(1).replace(",", ".")) if m else None


def _extract_size(text: str) -> int | None:
    m = re.search(r"(\d{2,3})\s*(?:m²|m2|sqm|square)", text, re.I)
    return int(m.group(1)) if m else None


def _extract_work_location(text: str) -> str | None:
    m = re.search(
        r"(?:work\s+(?:near|at|by|close to)|near|close to|around)\s+"
        r"([A-ZÄÖÜ][\wäöüß]+(?:\s+[A-ZÄÖÜ][\wäöüß]+)?)",
        text,
    )
    return m.group(1).strip() if m else None


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

    return {
        "max_warm_rent": _extract_rent(text),
        "min_rooms": _extract_rooms(text),
        "min_size_m2": _extract_size(text),
        "work_location": _extract_work_location(text),
        "transport_priority": any(k in low for k in _TRANSPORT_KEYWORDS),
        "quiet_priority": any(k in low for k in _QUIET_KEYWORDS),
        "desired_amenities": amenities,
        "furnished": furnished,
        "notes": text,  # never lose the original request in fallback mode
    }
