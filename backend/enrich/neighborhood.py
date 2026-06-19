"""Neighborhood insights (F6) — POI counts + summary via OSM Overpass.

Counts cafes/parks/supermarkets/nightlife/gyms/transit within a walking radius of a
listing, keeps the individual POIs (for a future map), and caches everything in
`neighborhood_cache`. Free, keyless API. Degrades gracefully: on failure returns None
and the amenity factor stays inactive.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from core.logging import get_logger
from data.models import NeighborhoodCache
from enrich.neighborhood_parse import (
    DEFAULT_RADIUS_M,
    NeighborhoodResult,
    build_overpass_query,
    parse_overpass,
    summarize,
)
from search.parse_rules import CANONICAL_AMENITIES

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OVERPASS_HEADERS = {
    "User-Agent": "wohniq/1.0",
    "Accept-Encoding": "identity",
}


def _location_key(lat: float, lng: float) -> str:
    return f"{round(lat, 4)},{round(lng, 4)}"


def _from_cache(row: NeighborhoodCache) -> NeighborhoodResult:
    counts = row.poi_counts or {}
    available = {c for c in counts if c in CANONICAL_AMENITIES and counts[c] >= 1}
    return NeighborhoodResult(
        counts=counts, pois=row.pois or [], summary=row.summary or "", available_amenities=available
    )


def get_neighborhood(
    session: Session,
    lat: float,
    lng: float,
    *,
    radius: int = DEFAULT_RADIUS_M,
    cache_only: bool = False,
) -> NeighborhoodResult | None:
    """Cached neighborhood insight for a coordinate, or None on failure.

    Pass cache_only=True to skip the live Overpass lookup (returns None when not cached).
    """
    location_key = _location_key(lat, lng)

    cached = session.get(NeighborhoodCache, location_key)
    if cached is not None:
        return _from_cache(cached)

    if cache_only:
        return None

    try:
        resp = httpx.post(
            OVERPASS_URL,
            data={"data": build_overpass_query(lat, lng, radius)},
            headers=_OVERPASS_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        result = parse_overpass(resp.json())
    except (httpx.HTTPError, ValueError) as exc:  # network/parse issues degrade gracefully
        logger.warning("neighborhood lookup failed (%s): %s", location_key, exc)
        return None

    session.add(
        NeighborhoodCache(
            location_key=location_key,
            poi_counts=result.counts,
            pois=result.pois,
            summary=result.summary,
        )
    )
    session.commit()
    return result


__all__ = ["get_neighborhood", "summarize", "NeighborhoodResult"]
