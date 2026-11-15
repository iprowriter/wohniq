"""Deterministic ranking (F3) — pure, no LLM, no DB (ADR-0001).

Scores each candidate listing against the user's criteria across independent
factors, each normalized to [0, 1], then combines them as a weighted average of the
*active* factors. A factor is active only when the user expressed that preference and
the data exists (e.g. quiet only counts if they asked for quiet AND we know the Kiez
nightlife). The output is a per-factor breakdown — the same numbers the explanation
layer (T2.7) turns into prose and the UI shows.

Determinism (ADR-0001 AC1): pure function, stable sort — same input always yields the
same order and the same breakdown.

Commute and neighborhood inputs arrive in M4 (T4.1/T4.2); until then those factors
simply stay inactive and ranking runs on relevance + budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from search.areas import NEARBY_MAX_KM

MAX_COMMUTE_MIN = 60  # commute at/above this scores 0
_NIGHTLIFE_QUIET = {"low": 1.0, "medium": 0.5, "high": 0.1}

# Area fit. In a requested area = 1.0. A "nearby" fallback listing scores at most
# NEARBY_MAX_SCORE, falling with distance — always below the caveat threshold, so being
# outside the asked-for areas is stated honestly, and closer ones still rank higher.
IN_AREA, NEARBY, OUTSIDE = "in_area", "nearby", "outside"
NEARBY_MAX_SCORE = 0.4


@dataclass(frozen=True)
class RankingWeights:
    relevance: float = 1.0
    budget: float = 1.5
    commute: float = 2.0  # live BVG/VBB journey
    # Offline estimates are less certain than live journeys, so they count less.
    # Route-based (VBB timetable network, ADR-0009) sits between straight-line and live.
    commute_network: float = 1.5
    commute_estimated: float = 1.0  # straight-line estimate (ADR-0008)
    quiet: float = 1.0
    amenities: float = 1.0
    area: float = 1.5


@dataclass
class RankingInput:
    """Facts about one candidate. Optional fields are filled by M4 enrichment."""

    warmmiete_eur: int
    distance: float = 0.0  # cosine distance from retrieval (smaller = more relevant)
    nightlife: str | None = None  # 'low' | 'medium' | 'high'
    available_amenities: set[str] | None = None
    commute_minutes: int | None = None
    commute_source: str = "live"  # "live" | "network" | "distance" (see CommuteResult)
    commute_changes: int | None = None
    listing_id: str | None = None  # so callers can map results back
    kiez: str | None = None  # for readable details ("Lichtenberg is a quiet Kiez")
    # Area fit, set when the user asked for areas: IN_AREA | NEARBY | OUTSIDE, the
    # requested area it's in (or nearest to), and the km from that area's centre.
    area_status: str | None = None
    area_name: str | None = None
    area_distance_km: float | None = None


@dataclass
class RankCriteria:
    max_warm_rent: int | None = None
    quiet_priority: bool = False
    desired_amenities: tuple[str, ...] = ()
    areas: tuple[str, ...] = ()


@dataclass
class FactorScore:
    name: str
    score: float  # 0..1
    weight: float
    detail: str  # human-readable, consumed by the explanation layer
    # Short phrase for the one-line summary ("€471 under your €1,000 budget").
    highlight: str = field(default="")


@dataclass
class RankingResult:
    total: float  # 0..1 weighted average of active factors
    factors: list[FactorScore]


def _changes(n: int | None) -> str:
    if not n:
        return "direct"
    return f"{n} change{'s' if n > 1 else ''}"


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def euro(amount: int) -> str:
    """€1.010 — the same German thousands separator the UI uses for prices."""
    return f"€{amount:,}".replace(",", ".")


def join_words(items: list[str], conj: str = "and") -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {conj} {items[-1]}"


def _area_factor(item: RankingInput, criteria: RankCriteria, weight: float) -> FactorScore:
    place = item.kiez or item.area_name or "this area"
    asked = join_words(list(criteria.areas), "or")
    if item.area_status == IN_AREA:
        where = place if place == item.area_name else f"{place} ({item.area_name})"
        if len(criteria.areas) > 1:
            detail, highlight = f"In {where}, one of the areas you asked for", f"in {where}"
        else:
            detail, highlight = f"In {where}, as you asked", f"in {where} as you asked"
        return FactorScore("area", 1.0, weight, detail, highlight=highlight)
    km = item.area_distance_km if item.area_distance_km is not None else NEARBY_MAX_KM * 2
    if item.area_status == NEARBY:
        score = NEARBY_MAX_SCORE * _clamp(1.0 - km / NEARBY_MAX_KM)
        detail = f"Not in {asked}: {place} is {km:.1f} km from {item.area_name}"
        highlight = f"near {item.area_name} ({place}, {km:.1f} km away)"
        return FactorScore("area", score, weight, detail, highlight=highlight)
    detail = f"Not in {asked}: {place} is {km:.1f} km away"
    return FactorScore("area", 0.0, weight, detail)


def _quiet_detail(nightlife: str, kiez: str | None) -> tuple[str, str]:
    if kiez is None:
        return f"{nightlife} nightlife", f"{nightlife} nightlife"
    if nightlife == "low":
        return f"{kiez} is a quiet Kiez with little nightlife", "a quiet Kiez with little nightlife"
    if nightlife == "medium":
        return f"{kiez} is fairly calm, with some nightlife", "a fairly calm Kiez"
    return f"{kiez} is lively, with lots of nightlife", "a lively Kiez"


def score_listing(
    item: RankingInput,
    criteria: RankCriteria,
    *,
    weights: RankingWeights | None = None,
) -> RankingResult:
    """Score one listing, returning the weighted total and the active-factor breakdown."""
    w = weights or RankingWeights()
    factors: list[FactorScore] = []

    # Relevance — always active (semantic closeness from retrieval).
    relevance = _clamp(1.0 - item.distance)
    factors.append(FactorScore("relevance", relevance, w.relevance, f"semantic match {relevance:.0%}"))

    # Area — only when the user named areas to live in.
    if criteria.areas and item.area_status:
        factors.append(_area_factor(item, criteria, w.area))

    # Budget fit — comfortably under budget scores higher; at-budget still fits.
    if criteria.max_warm_rent:
        budget = criteria.max_warm_rent
        headroom = _clamp((budget - item.warmmiete_eur) / budget)
        score = _clamp(0.6 + 0.4 * min(headroom / 0.3, 1.0))
        under = budget - item.warmmiete_eur
        warm = euro(item.warmmiete_eur)
        if under > 0:
            detail = f"{warm} warm, {euro(under)} under your {euro(budget)} budget"
            highlight = f"{euro(under)} under your {euro(budget)} budget"
        elif under == 0:
            detail = f"{warm} warm, right at your {euro(budget)} budget"
            highlight = f"within your {euro(budget)} budget"
        else:
            detail = f"{warm} warm, {euro(-under)} over your {euro(budget)} budget"
            highlight = ""
        factors.append(FactorScore("budget", score, w.budget, detail, highlight=highlight))

    # Commute — closer to work scores higher (M4 supplies the minutes).
    if item.commute_minutes is not None:
        score = _clamp(1.0 - item.commute_minutes / MAX_COMMUTE_MIN)
        if item.commute_source == "network":
            weight = w.commute_network
            changes = _changes(item.commute_changes)
            detail = f"≈{item.commute_minutes} min to work, {changes} (estimated)"
        elif item.commute_source == "distance":
            weight = w.commute_estimated
            detail = f"≈{item.commute_minutes} min to work (estimated)"
        else:
            weight, detail = w.commute, f"{item.commute_minutes} min to work"
        highlight = detail.split(",")[0].replace(" (estimated)", "")
        factors.append(FactorScore("commute", score, weight, detail, highlight=highlight))

    # Quiet — only if they asked for it and we know the Kiez nightlife.
    if criteria.quiet_priority and item.nightlife:
        score = _NIGHTLIFE_QUIET.get(item.nightlife, 0.5)
        detail, highlight = _quiet_detail(item.nightlife, item.kiez)
        factors.append(FactorScore("quiet", score, w.quiet, detail, highlight=highlight))

    # Amenities — fraction of desired tags present nearby.
    if criteria.desired_amenities and item.available_amenities is not None:
        desired = list(dict.fromkeys(criteria.desired_amenities))  # keep the user's order
        matched = [a for a in desired if a in item.available_amenities]
        missing = [a for a in desired if a not in item.available_amenities]
        score = len(matched) / len(desired)
        if not matched:
            detail = f"No {join_words(desired, 'or')} nearby"
        elif missing:
            no = join_words(missing, "or")
            detail = f"{join_words(matched).capitalize()} nearby, but no {no}"
        else:
            detail = f"{join_words(matched).capitalize()} nearby"
        highlight = f"{join_words(matched)} nearby" if matched else ""
        factors.append(FactorScore("amenities", score, w.amenities, detail, highlight=highlight))

    total_weight = sum(f.weight for f in factors)
    total = sum(f.score * f.weight for f in factors) / total_weight if total_weight else 0.0
    return RankingResult(total=total, factors=factors)


def rank(
    items: list[RankingInput],
    criteria: RankCriteria,
    *,
    weights: RankingWeights | None = None,
) -> list[tuple[RankingInput, RankingResult]]:
    """Score and order candidates best-first. Stable: ties keep input order."""
    scored = [(item, score_listing(item, criteria, weights=weights)) for item in items]
    scored.sort(key=lambda pair: pair[1].total, reverse=True)
    return scored
