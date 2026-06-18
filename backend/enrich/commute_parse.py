"""Parse a transport.rest journey into a commute summary (pure, stdlib only).

Turns the BVG/VBB journeys response into door-to-door minutes, number of changes,
and walking minutes. Kept separate from the HTTP client so the parsing — the fiddly
part — is unit-testable against sample payloads without the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CommuteResult:
    minutes: int
    changes: int
    walk_minutes: int | None


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_journey(journey: dict) -> CommuteResult | None:
    """Door-to-door minutes, changes, and walking minutes from one journey.

    A journey is a list of legs; transit legs carry a `line`, walking legs are flagged
    `walking: true`. Changes = transit legs − 1.
    """
    legs = journey.get("legs") or []
    timed = [leg for leg in legs if leg.get("departure") and leg.get("arrival")]
    if not timed:
        return None

    total_minutes = round((_dt(timed[-1]["arrival"]) - _dt(timed[0]["departure"])).total_seconds() / 60)

    transit_legs = [leg for leg in legs if leg.get("line")]
    changes = max(0, len(transit_legs) - 1)

    walk = 0.0
    for leg in legs:
        if leg.get("walking") and leg.get("departure") and leg.get("arrival"):
            walk += (_dt(leg["arrival"]) - _dt(leg["departure"])).total_seconds() / 60
    walk_minutes = round(walk) if walk else None

    return CommuteResult(minutes=total_minutes, changes=changes, walk_minutes=walk_minutes)
