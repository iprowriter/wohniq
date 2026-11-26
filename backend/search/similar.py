"""Similar apartments to a listing (T9.7, SPEC F13).

Deterministic and explainable (golden rule 1: code ranks, never the LLM). Each candidate gets
a weighted score from named factors (distance, rooms, size, warm rent, furnished, building
period); each card says in words why it is similar, and every reason is computed from the
same numbers. High-risk listings are included (owner's decision) and carry their risk chip
on the page; only the flat itself and copies reusing its photo set are left out.

When the flat asks more than the rent-brake limit, flats within the limit come first.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Weights of the named factors (sum 10). Distance counts most: "similar" in a flat search
# mostly means "in the same part of town".
WEIGHTS: dict[str, float] = {
    "distance": 3.0,
    "rooms": 2.0,
    "size": 2.0,
    "rent": 2.0,
    "furnished": 0.5,
    "period": 0.5,
}
DISTANCE_SCALE_KM = 2.5  # score e^(-d/scale): 1 km ≈ 0.67, 3 km ≈ 0.30
TOLERANCE = 0.2  # size and rent: ±20 % still counts as similar
FAIR = frozenset({"within_limit", "below_index"})


@dataclass(frozen=True)
class Flat:
    """What similarity looks at, independent of the ORM (tests build these directly)."""

    id: str
    lat: float
    lng: float
    rooms: float
    size_m2: int
    warm_eur: int
    furnished: bool = False
    planning_area: str | None = None
    district: str | None = None
    period: str | None = None  # Mietspiegel building period
    rent_verdict: str | None = None
    photo_set_id: str | None = None


@dataclass(frozen=True)
class Similar:
    id: str
    score: float  # 0..1
    distance_km: float
    reasons: list[str] = field(default_factory=list)
    fair_rent: bool = False


def _km(a: Flat, b: Flat) -> float:
    r = 6371.0088
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _closeness(value: float, target: float) -> float:
    """1 when equal, 0 at ±TOLERANCE (relative) or beyond."""
    if target <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(value - target) / (TOLERANCE * target))


def _rooms_score(a: float, b: float) -> float:
    diff = abs(a - b)
    return 1.0 if diff == 0 else 0.6 if diff <= 0.5 else 0.25 if diff <= 1 else 0.0


def _fmt_rooms(r: float) -> str:
    n = f"{r:g}"
    return f"{n} room" if r == 1 else f"{n} rooms"


def factors(target: Flat, other: Flat) -> dict[str, float]:
    return {
        "distance": math.exp(-_km(target, other) / DISTANCE_SCALE_KM),
        "rooms": _rooms_score(target.rooms, other.rooms),
        "size": _closeness(other.size_m2, target.size_m2),
        "rent": _closeness(other.warm_eur, target.warm_eur),
        "furnished": 1.0 if other.furnished == target.furnished else 0.0,
        "period": 1.0 if target.period and other.period == target.period else 0.0,
    }


def reasons(target: Flat, other: Flat, distance_km: float) -> list[str]:
    """Why it's similar, in plain words; every phrase restates a number above."""
    out: list[str] = []
    where = f"{distance_km:.1f} km away"
    if target.planning_area and other.planning_area == target.planning_area:
        out.append(f"Same area · {where}")
    elif target.district and other.district == target.district:
        out.append(f"Same district · {where}")
    else:
        out.append(where.capitalize())
    out.append(
        f"{_fmt_rooms(other.rooms)}, {other.size_m2} m² "
        f"(this: {_fmt_rooms(target.rooms)}, {target.size_m2} m²)"
    )
    diff = other.warm_eur - target.warm_eur
    if abs(diff) < 10:
        out.append("About the same warm rent")
    else:
        out.append(f"€{abs(diff):,} {'less' if diff < 0 else 'more'} warm")
    if other.rent_verdict in FAIR:
        out.append("Fair rent")
    return out


def rank_similar(
    target: Flat, candidates: list[Flat], limit: int = 12
) -> tuple[list[Similar], bool]:
    """The most similar flats, and whether "within the rent limit" ones were put first."""
    total = sum(WEIGHTS.values())
    scored: list[Similar] = []
    for c in candidates:
        if c.id == target.id:
            continue
        if target.photo_set_id and c.photo_set_id == target.photo_set_id:
            continue  # a copy reusing the same photos is not "another flat"
        f = factors(target, c)
        score = sum(WEIGHTS[k] * v for k, v in f.items()) / total
        d = _km(target, c)
        scored.append(
            Similar(
                id=c.id,
                score=round(score, 4),
                distance_km=round(d, 2),
                reasons=reasons(target, c, d),
                fair_rent=c.rent_verdict in FAIR,
            )
        )
    fair_first = target.rent_verdict == "above_limit" and any(s.fair_rent for s in scored)
    # Deterministic: score, then distance, then id.
    scored.sort(
        key=lambda s: (not s.fair_rent if fair_first else False, -s.score, s.distance_km, s.id)
    )
    return scored[:limit], fair_first
