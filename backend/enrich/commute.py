"""Commute analysis (F5) — door-to-door public-transport time via BVG/VBB.

Uses the free, keyless transport.rest VBB API: resolve the work location to a stop,
then ask for a journey from the listing's coordinates. Results are cached per
(origin, destination) in `commute_cache` so repeated lookups are instant and offline.

When the live lookup fails (network/API error, or no journey found) we fall back to an
offline estimate instead of showing nothing: routed over the VBB weekday-peak network
when it has been downloaded (enrich/transit_network.py, ADR-0009), else from straight-line
distance (enrich/commute_estimate.py, ADR-0008). The destination is the stop the API
resolved, if it got that far, else the local place index. Estimates are flagged
(`source` != "live") and never written to `commute_cache`, so an outage can't be cached
as if it were a real journey.
"""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from core.logging import get_logger
from data.models import CommuteCache
from enrich.commute_estimate import estimate_commute
from enrich.commute_parse import CommuteResult, parse_journey
from enrich.places import resolve_place
from enrich.transit_network import get_network

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


def fetch_first_journey(
    from_lat: float, from_lng: float, to_stop_id: str, *, departure: str | None = None
) -> dict | None:
    """First journey to a stop; `departure` is an ISO 8601 time (default: now)."""
    params = {
        "from.latitude": from_lat,
        "from.longitude": from_lng,
        "from.address": "Listing",
        "to": to_stop_id,
        "results": 1,
        "stopovers": "false",
    }
    if departure:
        params["departure"] = departure
    resp = httpx.get(
        f"{BASE_URL}/journeys",
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    journeys = resp.json().get("journeys") or []
    return journeys[0] if journeys else None


def _stop_coords(stop: dict | None) -> tuple[float, float] | None:
    """Coordinates of a transport.rest location (stops nest them under "location")."""
    if not stop:
        return None
    loc = stop.get("location") or stop
    lat, lng = loc.get("latitude"), loc.get("longitude")
    return (float(lat), float(lng)) if lat is not None and lng is not None else None


def estimate_commute_to(
    lat: float,
    lng: float,
    work_location: str | None,
    *,
    destination: tuple[float, float] | None = None,
) -> CommuteResult | None:
    """Offline estimate to the work location; None if we can't place it. No network."""
    if destination is None:
        place = resolve_place(work_location) if work_location else None
        if place is None:
            return None
        destination = (place.lat, place.lng)
    return estimate_between(lat, lng, *destination)


def estimate_between(lat: float, lng: float, dlat: float, dlng: float) -> CommuteResult:
    """Route-based estimate when the VBB network is available, else straight-line."""
    straight = estimate_commute(lat, lng, dlat, dlng)
    net = get_network()
    if net is None:
        return straight
    route = net.route(lat, lng, dlat, dlng)
    # Walking-only "routes" (no stations nearby) can be far slower than riding something
    # we don't know about; then the straight-line estimate is the better guess.
    if not route.uses_transit and route.minutes > straight.minutes:
        return straight
    return CommuteResult(
        minutes=max(1, round(route.minutes)),
        changes=route.changes,
        walk_minutes=round(route.walk_minutes),
        source="network",
    )


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

    stop: dict | None = None
    result: CommuteResult | None = None
    try:
        stop = resolve_location(work_location)
        if stop and "id" in stop:
            journey = fetch_first_journey(lat, lng, stop["id"])
            result = parse_journey(journey) if journey else None
    except (httpx.HTTPError, ValueError) as exc:  # network/parse issues degrade gracefully
        logger.warning("commute lookup failed (%s → %s): %s", origin_key, dest_key, exc)

    if result is None:
        # Show an estimate rather than nothing; deliberately not cached.
        return estimate_commute_to(lat, lng, work_location, destination=_stop_coords(stop))

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
