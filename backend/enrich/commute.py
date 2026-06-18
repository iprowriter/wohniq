"""Commute analysis (F5) — door-to-door public-transport time via BVG/VBB.

Uses the free, keyless transport.rest VBB API: resolve the work location to a stop,
then ask for a journey from the listing's coordinates. Results are cached per
(origin, destination) in `commute_cache` so repeated lookups are instant and offline.
Degrades gracefully: any API/parse failure returns None and the commute factor simply
stays inactive (the ranker handles that).
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from core.logging import get_logger
from data.models import CommuteCache
from enrich.commute_parse import CommuteResult, parse_journey

logger = get_logger(__name__)

# VBB covers Berlin + Brandenburg; keyless community API. No secret needed.
BASE_URL = "https://v6.vbb.transport.rest"


def _origin_key(lat: float, lng: float) -> str:
    return f"{round(lat, 4)},{round(lng, 4)}"


def resolve_location(query: str) -> dict | None:
    """Resolve a free-text place name to a transit stop."""
    resp = httpx.get(
        f"{BASE_URL}/locations",
        params={"query": query, "results": 1, "fuzzy": "true", "addresses": "false", "poi": "false"},
        timeout=15,
    )
    resp.raise_for_status()
    items = resp.json()
    return items[0] if items else None


def fetch_first_journey(from_lat: float, from_lng: float, to_stop_id: str) -> dict | None:
    resp = httpx.get(
        f"{BASE_URL}/journeys",
        params={
            "from.latitude": from_lat,
            "from.longitude": from_lng,
            "from.address": "Listing",
            "to": to_stop_id,
            "results": 1,
            "stopovers": "false",
        },
        timeout=20,
    )
    resp.raise_for_status()
    journeys = resp.json().get("journeys") or []
    return journeys[0] if journeys else None


def _fetch_commute(lat: float, lng: float, work_location: str) -> CommuteResult | None:
    stop = resolve_location(work_location)
    if not stop or "id" not in stop:
        return None
    journey = fetch_first_journey(lat, lng, stop["id"])
    return parse_journey(journey) if journey else None


def get_commute(
    session: Session,
    lat: float,
    lng: float,
    work_location: str | None,
) -> CommuteResult | None:
    """Cached door-to-door commute from a listing to the work location, or None."""
    if not work_location:
        return None

    origin_key = _origin_key(lat, lng)
    dest_key = work_location.strip().lower()

    cached = session.get(CommuteCache, (origin_key, dest_key))
    if cached is not None:
        return CommuteResult(cached.minutes, cached.changes, cached.walk_minutes)

    try:
        result = _fetch_commute(lat, lng, work_location)
    except (httpx.HTTPError, ValueError) as exc:  # network/parse issues degrade gracefully
        logger.warning("commute lookup failed (%s → %s): %s", origin_key, dest_key, exc)
        return None

    if result is None:
        return None

    session.add(
        CommuteCache(
            origin_key=origin_key,
            dest_key=dest_key,
            minutes=result.minutes,
            changes=result.changes,
            walk_minutes=result.walk_minutes,
        )
    )
    session.commit()
    return result
