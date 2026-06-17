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

from dataclasses import dataclass

MAX_COMMUTE_MIN = 60  # commute at/above this scores 0
_NIGHTLIFE_QUIET = {"low": 1.0, "medium": 0.5, "high": 0.1}


@dataclass(frozen=True)
class RankingWeights:
    relevance: float = 1.0
    budget: float = 1.5
    commute: float = 2.0
    quiet: float = 1.0
    amenities: float = 1.0


@dataclass
class RankingInput:
    """Facts about one candidate. Optional fields are filled by M4 enrichment."""

    warmmiete_eur: int
    distance: float = 0.0  # cosine distance from retrieval (smaller = more relevant)
    nightlife: str | None = None  # 'low' | 'medium' | 'high'
    available_amenities: set[str] | None = None
    commute_minutes: int | None = None
    listing_id: str | None = None  # so callers can map results back


@dataclass
class RankCriteria:
    max_warm_rent: int | None = None
    quiet_priority: bool = False
    desired_amenities: tuple[str, ...] = ()


@dataclass
class FactorScore:
    name: str
    score: float  # 0..1
    weight: float
    detail: str  # human-readable, consumed by the explanation layer


@dataclass
class RankingResult:
    total: float  # 0..1 weighted average of active factors
    factors: list[FactorScore]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


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

    # Budget fit — comfortably under budget scores higher; at-budget still fits.
    if criteria.max_warm_rent:
        budget = criteria.max_warm_rent
        headroom = _clamp((budget - item.warmmiete_eur) / budget)
        score = _clamp(0.6 + 0.4 * min(headroom / 0.3, 1.0))
        under = budget - item.warmmiete_eur
        detail = f"€{under} under budget" if under > 0 else "at budget"
        factors.append(FactorScore("budget", score, w.budget, detail))

    # Commute — closer to work scores higher (M4 supplies the minutes).
    if item.commute_minutes is not None:
        score = _clamp(1.0 - item.commute_minutes / MAX_COMMUTE_MIN)
        factors.append(
            FactorScore("commute", score, w.commute, f"{item.commute_minutes} min to work")
        )

    # Quiet — only if they asked for it and we know the Kiez nightlife.
    if criteria.quiet_priority and item.nightlife:
        score = _NIGHTLIFE_QUIET.get(item.nightlife, 0.5)
        factors.append(FactorScore("quiet", score, w.quiet, f"{item.nightlife} nightlife"))

    # Amenities — fraction of desired tags present nearby.
    if criteria.desired_amenities and item.available_amenities is not None:
        desired = set(criteria.desired_amenities)
        matched = desired & item.available_amenities
        score = len(matched) / len(desired)
        factors.append(
            FactorScore(
                "amenities", score, w.amenities, f"{len(matched)} of {len(desired)} amenities nearby"
            )
        )

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
