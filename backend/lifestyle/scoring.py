"""Lifestyle Match scoring: weights × region profiles → a ranked list (ADR-0011).

Pure and deterministic (ADR-0001): no LLM, no I/O, same input → same output.

For each region and each attribute the user weighted (> 0):
  * area attributes: the bundle's fixed normalisation (lifestyle.profiles.score);
  * affordability: typical warm rent for the user's flat size vs. their budget;
  * commute: precomputed public-transport minutes to the chosen destination vs. the
    user's maximum.
Both personal factors use the same shape, `limit_score`: full marks when comfortably
inside the limit, half marks exactly at it, zero well beyond it.

    total = Σ weight·score / Σ weight      (over factors with data; shown as 0–100)

Ranking (lexicographic): every region where a typical flat fits the budget comes before
any region over budget — over-budget areas are still shown, just ranked lower. Within
each of those, regions inside the user's maximum commute come first. Then higher total
first, ties broken by region key, so the order is stable.

Each region is scored on its own data only, so removing a region from the results
(or excluding it) can never change any other region's score.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from lifestyle.attributes import ATTRIBUTES_BY_ID
from lifestyle.profiles import CommuteTime, ProfileBundle, Region
from lifestyle.questionnaire import Answers
from lifestyle.weights import Weights

AFFORDABLE_COMFORT = 0.70  # warm rent ≤ 70% of budget → full marks
AFFORDABLE_ZERO = 1.30  # ≥ 130% of budget → zero
COMMUTE_COMFORT_MIN = 10  # ≤ 10 minutes → full marks
COMMUTE_ZERO_FACTOR = 1.5  # ≥ 1.5 × the user's maximum → zero


class MatchError(ValueError):
    """Invalid request for the data we have (unknown destination/region, no weights)."""


def limit_score(value: float, comfortable: float, limit: float, zero: float) -> float:
    """1 up to `comfortable`, 0.5 at `limit`, 0 from `zero`; linear in between."""
    if value <= comfortable:
        return 1.0
    if value <= limit:
        return 1.0 - 0.5 * (value - comfortable) / (limit - comfortable)
    if value < zero:
        return 0.5 * (zero - value) / (zero - limit)
    return 0.0


@dataclass(frozen=True)
class Factor:
    attribute: str
    label: str
    weight: int
    score: float  # 0..1
    contribution: float  # weight·score / Σ weight — its share of the total
    raw: float
    unit: str
    source_id: str
    year: str
    berlin: float | None = None  # Berlin-wide reference, when meaningful


@dataclass(frozen=True)
class RegionMatch:
    rank: int
    region: Region
    total: float  # 0..1
    factors: list[Factor]
    warm_rent_eur: int  # typical warm rent for the user's flat size
    fits_budget: bool
    commute: CommuteTime | None
    within_commute: bool | None  # None when no destination was chosen

    @property
    def tier(self) -> tuple[bool, bool]:
        """Sort first by budget, then by commute limit (False sorts before True)."""
        return (not self.fits_budget, self.within_commute is False)


@dataclass(frozen=True)
class MatchResult:
    results: list[RegionMatch]
    weights: dict[str, int]  # the weights actually used
    unscored: dict[str, str] = field(default_factory=dict)  # attribute -> why not scored
    excluded: list[str] = field(default_factory=list)


def typical_warm_rent(bundle: ProfileBundle, region: Region, size_m2: int) -> int:
    """District median asking rent + average operating costs, for the user's flat size."""
    running = bundle.city["operating_costs_cold"].value + bundle.city["operating_costs_warm"].value
    cold = region.rent.raw if region.rent else bundle.city["asking_rent_median"].value
    return round((cold + running) * size_m2)


def _area_factor(bundle: ProfileBundle, region: Region, attribute: str) -> dict | None:
    measure = region.measures.get(attribute)
    if measure is None:
        return None
    ref = bundle.references[attribute]
    return dict(
        score=bundle.score(attribute, measure.raw),
        raw=measure.raw,
        unit=measure.unit,
        source_id=measure.source_id,
        year=measure.year,
        berlin=ref.berlin,
    )


def score_region(
    bundle: ProfileBundle, region: Region, answers: Answers, weights: dict[str, int]
) -> tuple[float, list[Factor], int, CommuteTime | None]:
    """Total (0..1), factors, typical warm rent, and commute for one region."""
    warm = typical_warm_rent(bundle, region, answers.size_m2)
    commute = bundle.commute_time(answers.destination, region.key) if answers.destination else None
    partial: list[tuple[str, int, dict]] = []
    for attribute, weight in weights.items():
        if weight <= 0:
            continue
        if attribute == "affordability":
            budget = answers.budget_eur
            data = dict(
                score=limit_score(
                    warm, AFFORDABLE_COMFORT * budget, budget, AFFORDABLE_ZERO * budget
                ),
                raw=float(warm),
                unit="EUR/month warm (typical, for your flat size)",
                source_id=region.rent.source_id if region.rent else "ibb_wohnungsmarktbericht_2025",
                year="2025",
                berlin=float(typical_warm_rent_berlin(bundle, answers.size_m2)),
            )
        elif attribute == "commute":
            if commute is None:
                continue
            limit = answers.max_commute_min
            comfortable = min(COMMUTE_COMFORT_MIN, limit / 2)
            data = dict(
                score=limit_score(commute.minutes, comfortable, limit, COMMUTE_ZERO_FACTOR * limit),
                raw=float(commute.minutes),
                unit="minutes by public transport",
                source_id=bundle.commute.source_id if bundle.commute else "vbb_gtfs",
                year="2026",
                berlin=None,
            )
        else:
            data = _area_factor(bundle, region, attribute)
            if data is None:
                continue
        partial.append((attribute, weight, data))

    total_weight = sum(w for _, w, _ in partial)
    factors = [
        Factor(
            attribute=a,
            label=ATTRIBUTES_BY_ID[a].label,
            weight=w,
            contribution=(w * d["score"] / total_weight) if total_weight else 0.0,
            **d,
        )
        for a, w, d in partial
    ]
    total = sum(f.contribution for f in factors)
    factors.sort(key=lambda f: (-f.contribution, f.attribute))
    return total, factors, warm, commute


def typical_warm_rent_berlin(bundle: ProfileBundle, size_m2: int) -> int:
    running = bundle.city["operating_costs_cold"].value + bundle.city["operating_costs_warm"].value
    return round((bundle.city["asking_rent_median"].value + running) * size_m2)


def unscored_attributes(
    bundle: ProfileBundle, answers: Answers, weights: dict[str, int]
) -> dict[str, str]:
    """Weighted attributes we can't score, with a user-facing reason."""
    out: dict[str, str] = {}
    for attribute, weight in weights.items():
        if weight <= 0:
            continue
        if attribute == "commute":
            if not answers.destination:
                out[attribute] = "Pick a destination to score commute times."
            elif bundle.commute is None:
                out[attribute] = "Commute times are not available in this data build."
        elif attribute != "affordability" and attribute not in bundle.references:
            out[attribute] = "No data for this attribute yet."
    return out


def match(
    bundle: ProfileBundle,
    answers: Answers,
    weights: Weights,
    *,
    excluded: list[str] | tuple[str, ...] = (),
    limit: int | None = None,
) -> MatchResult:
    """Rank every region (except `excluded`) for these answers and weights."""
    if answers.destination and bundle.destination(answers.destination) is None:
        raise MatchError(f"Unknown destination {answers.destination!r}")
    known = {r.key for r in bundle.regions}
    unknown = [k for k in excluded if k not in known]
    if unknown:
        raise MatchError(f"Unknown region key(s): {unknown}")
    active = weights.active()
    unscored = unscored_attributes(bundle, answers, active)
    if not any(a not in unscored for a in active):
        raise MatchError("Give at least one scorable attribute a weight above 0.")

    scored: list[RegionMatch] = []
    skip = set(excluded)
    for region in bundle.regions:
        if region.key in skip:
            continue
        total, factors, warm, commute = score_region(bundle, region, answers, active)
        within = None if commute is None else commute.minutes <= answers.max_commute_min
        scored.append(
            RegionMatch(
                rank=0,
                region=region,
                total=total,
                factors=factors,
                warm_rent_eur=warm,
                fits_budget=warm <= answers.budget_eur,
                commute=commute,
                within_commute=within,
            )
        )
    scored.sort(key=lambda m: (m.tier, -round(m.total, 9), m.region.key))
    ranked = [replace(m, rank=i + 1) for i, m in enumerate(scored)]
    if limit is not None:
        ranked = ranked[:limit]
    return MatchResult(results=ranked, weights=active, unscored=unscored, excluded=sorted(skip))
