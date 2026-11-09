"""Offline commute estimate (pure, stdlib only) — used when live transit data isn't available.

Door-to-door public-transport time from straight-line (haversine) distance, using
published average speeds for Berlin's transit modes. It's an *estimate*: results are
flagged `source="distance"` (so `estimated` is True), rounded to 5 minutes, weighted
lower in ranking, and labelled in the UI. It's the fallback when the VBB network isn't
downloaded (the route-based estimate, ADR-0009, is preferred). Rationale and the full
list of assumptions: docs/adr/0008-offline-commute-estimate.md.

Model (d = straight-line km between listing and destination):

    walk    = d × WALK_DETOUR / WALK_KMH
    transit = ACCESS_EGRESS_MIN + INITIAL_WAIT_MIN
              + in-vehicle time for d × TRANSIT_DETOUR, where the first 2 km run at
                bus/tram speed, the next 4 km at U-Bahn speed, and the rest at S-Bahn
                speed (longer trips use faster modes; marginal "brackets" keep the
                result continuous and increasing with distance)
              + TRANSFER_MIN if d ≥ TRANSFER_FROM_KM
    minutes = min(walk, transit), rounded to the nearest 5 (minimum 5)

Only minutes are reported: the number of changes is a guess, so it's not exposed.
"""

from __future__ import annotations

import math

from enrich.commute_parse import CommuteResult

EARTH_RADIUS_KM = 6371.0088  # mean Earth radius (IUGG)

# Published average operating speeds, including stops (approximate, rounded).
# Sources: BVG and S-Bahn Berlin published figures (see ADR-0008 for the table).
BUS_TRAM_KMH = 19.0
UBAHN_KMH = 31.0
SBAHN_KMH = 39.0

# Modelling assumptions (not published figures; documented in ADR-0008).
WALK_KMH = 4.8  # common planning value for walking speed (~1.3 m/s)
WALK_DETOUR = 1.3  # street grid vs. straight line
TRANSIT_DETOUR = 1.2  # rail/bus routes are fairly direct vs. straight line
ACCESS_EGRESS_MIN = 8.0  # walking to the first stop and from the last stop, combined
INITIAL_WAIT_MIN = 4.0  # about half a typical 5–10 minute headway
TRANSFER_FROM_KM = 5.0  # trips at least this long are assumed to need one change
TRANSFER_MIN = 4.0  # walk + wait for that change

# Distance brackets (straight-line km) → speed for that part of the trip.
_BRACKETS: tuple[tuple[float, float], ...] = (
    (2.0, BUS_TRAM_KMH),
    (4.0, UBAHN_KMH),
    (math.inf, SBAHN_KMH),
)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km. Well under 1% error at city scale."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def walk_minutes(distance_km: float) -> float:
    return distance_km * WALK_DETOUR / WALK_KMH * 60


def transit_minutes(distance_km: float) -> float:
    remaining = distance_km
    in_vehicle = 0.0
    for span_km, kmh in _BRACKETS:
        part = min(remaining, span_km)
        in_vehicle += part * TRANSIT_DETOUR / kmh * 60
        remaining -= part
        if remaining <= 0:
            break
    transfer = TRANSFER_MIN if distance_km >= TRANSFER_FROM_KM else 0.0
    return ACCESS_EGRESS_MIN + INITIAL_WAIT_MIN + in_vehicle + transfer


def round_to_5(minutes: float) -> int:
    return max(5, int(5 * round(minutes / 5)))


def estimate_commute(lat1: float, lng1: float, lat2: float, lng2: float) -> CommuteResult:
    """Estimated door-to-door minutes between two points (walk or transit, whichever is faster)."""
    distance = haversine_km(lat1, lng1, lat2, lng2)
    minutes = min(walk_minutes(distance), transit_minutes(distance))
    return CommuteResult(
        minutes=round_to_5(minutes), changes=None, walk_minutes=None, source="distance"
    )
