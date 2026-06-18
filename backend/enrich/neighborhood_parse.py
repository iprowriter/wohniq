"""Neighborhood insight parsing (pure, stdlib only).

Builds the Overpass query, parses its JSON into per-category counts AND the
individual POIs (category, name, lat, lng — kept for a future map), derives which
canonical amenities are present, and writes a short qualitative summary. All
deterministic and testable without the network (the HTTP call lives in neighborhood.py).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from search.parse_rules import CANONICAL_AMENITIES

# category -> list of (osm_key, {accepted values}). Used to build the query and to
# categorize returned elements.
CATEGORY_RULES: dict[str, list[tuple[str, set[str]]]] = {
    "cafes": [("amenity", {"cafe"})],
    "parks": [("leisure", {"park", "garden"})],
    "supermarket": [("shop", {"supermarket"})],
    "nightlife": [("amenity", {"bar", "pub", "nightclub"})],
    "gym": [("leisure", {"fitness_centre"}), ("amenity", {"gym"})],
    "transit": [("railway", {"station"}), ("public_transport", {"station"})],
}

DEFAULT_RADIUS_M = 500


@dataclass
class NeighborhoodResult:
    counts: dict[str, int]
    pois: list[dict]  # {category, name, lat, lng}
    summary: str
    available_amenities: set[str] = field(default_factory=set)


def build_overpass_query(lat: float, lng: float, radius: int = DEFAULT_RADIUS_M) -> str:
    """Overpass QL: every category's POIs within `radius` of (lat, lng)."""
    parts = []
    for rules in CATEGORY_RULES.values():
        for key, values in rules:
            for value in sorted(values):
                parts.append(f'  nwr(around:{radius},{lat},{lng})["{key}"="{value}"];')
    body = "\n".join(parts)
    return f"[out:json][timeout:25];\n(\n{body}\n);\nout center tags;"


def _categorize(tags: dict) -> str | None:
    for category, rules in CATEGORY_RULES.items():
        for key, values in rules:
            if tags.get(key) in values:
                return category
    return None


def _coords(element: dict) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return element["lat"], element["lon"]
    center = element.get("center")
    if center and "lat" in center and "lon" in center:
        return center["lat"], center["lon"]
    return None


def summarize(counts: dict[str, int]) -> str:
    if sum(counts.values()) == 0:
        return "Residential"  # nothing notable nearby
    descriptors: list[str] = []
    nightlife = counts.get("nightlife", 0)
    if nightlife <= 1:
        descriptors.append("quiet")
    elif nightlife >= 6:
        descriptors.append("lively")
    if counts.get("cafes", 0) >= 5:
        descriptors.append("cafe-rich")
    if counts.get("parks", 0) >= 1:
        descriptors.append("green")
    if counts.get("transit", 0) >= 1:
        descriptors.append("well-connected")
    if not descriptors:
        return "Residential"
    phrase = ", ".join(descriptors)
    return phrase[0].upper() + phrase[1:]


def parse_overpass(data: dict) -> NeighborhoodResult:
    """Parse an Overpass response into counts, POIs, availability, and a summary."""
    pois: list[dict] = []
    for element in data.get("elements", []):
        tags = element.get("tags") or {}
        category = _categorize(tags)
        if category is None:
            continue
        coords = _coords(element)
        if coords is None:
            continue
        pois.append(
            {
                "category": category,
                "name": tags.get("name"),
                "lat": coords[0],
                "lng": coords[1],
            }
        )

    counts = dict(Counter(p["category"] for p in pois))
    available = {c for c in counts if c in CANONICAL_AMENITIES and counts[c] >= 1}
    return NeighborhoodResult(
        counts=counts,
        pois=pois,
        summary=summarize(counts),
        available_amenities=available,
    )
