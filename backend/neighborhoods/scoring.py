"""Scoring and ranking Berlin's neighbourhoods — pure, deterministic, no LLM (ADR-0013).

1. **Metric score (0–100)** = the share of Berlin's 143 areas this area does better than on
   that metric, read against the *fixed* distribution stored in the bundle (ties count
   half). 100 = best in Berlin, 0 = worst, 50 = middle. Percentiles are robust to
   outliers (Tiergarten Süd's crime rate doesn't squash everyone else) and mean the same
   thing for every metric.
2. **Category score** = weighted mean of its metric scores (weights in catalog.METRICS).
3. **Overall score** = weighted mean of the category scores; weights 0–3 per category,
   defaults in catalog.CATEGORIES, adjustable by the user.
4. **Ranking**: by score (rounded to 0.1, so float noise never splits a tie), then by name.
   Equal scores share a rank (1, 2, 2, 4). Ranks are always Berlin-wide; filtering the
   list (e.g. by district) never changes any area's score or rank.
5. **Tiers**: the top 20% of ranks get the category's best label ("Lowest crime"), the
   bottom 20% its worst label ("Highest crime").
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from neighborhoods.bundle import Area, NeighbourhoodBundle, Value
from neighborhoods.catalog import (
    CATEGORIES,
    CATEGORIES_BY_ID,
    MAX_WEIGHT,
    OVERALL,
    Category,
    Metric,
    metrics_of,
)

Tier = Literal["best", "middle", "worst"]
TIER_SHARE = 0.2


class RankingError(ValueError):
    """Bad request: unknown category, bad weights."""


@dataclass(frozen=True)
class MetricScore:
    metric: Metric
    value: Value
    score: float  # 0..100
    berlin: float


@dataclass(frozen=True)
class CategoryScore:
    category: Category
    score: float | None  # 0..100; None when no scored metric has data
    metrics: tuple[MetricScore, ...]


@dataclass(frozen=True)
class Ranked:
    area: Area
    rank: int
    score: float
    tier: Tier


def percentile(distribution: Sequence[float], raw: float, higher_is_better: bool) -> float:
    """0..1: share of the other values `raw` beats (ties count half)."""
    n = len(distribution)
    if n < 2:
        raise ValueError("need at least two values")
    lo, hi = bisect_left(distribution, raw), bisect_right(distribution, raw)
    worse = lo if higher_is_better else n - hi
    ties = max(hi - lo - 1, 0)  # other areas with exactly this value
    return max(0.0, min(1.0, (worse + ties / 2) / (n - 1)))


def metric_score(bundle: NeighbourhoodBundle, metric: Metric, value: Value) -> MetricScore:
    ref = bundle.references[metric.id]
    pct = percentile(ref.distribution, value.raw, metric.higher_is_better)
    return MetricScore(metric, value, 100 * pct, ref.berlin)


def category_score(bundle: NeighbourhoodBundle, area: Area, category: Category) -> CategoryScore:
    scored = tuple(
        metric_score(bundle, m, area.values[m.id])
        for m in metrics_of(category.id)
        if m.id in area.values
    )
    weighted = [(s.score, s.metric.weight) for s in scored if s.metric.weight > 0]
    total_w = sum(w for _, w in weighted)
    score = sum(s * w for s, w in weighted) / total_w if total_w else None
    return CategoryScore(category, score, scored)


def category_table(bundle: NeighbourhoodBundle) -> dict[str, dict[str, CategoryScore]]:
    """area key -> category id -> score. Independent of user weights, so computed once."""
    cached = bundle.__dict__.get("_category_table")
    if cached is None:
        cached = {
            a.key: {c.id: category_score(bundle, a, c) for c in CATEGORIES} for a in bundle.regions
        }
        bundle.__dict__["_category_table"] = cached
    return cached


def default_weights() -> dict[str, int]:
    return {c.id: c.default_weight for c in CATEGORIES}


def validate_weights(weights: Mapping[str, int] | None) -> dict[str, int]:
    """Defaults overridden by the given weights; each 0..MAX_WEIGHT, at least one > 0."""
    out = default_weights()
    for cid, w in (weights or {}).items():
        if cid not in CATEGORIES_BY_ID:
            raise RankingError(f"unknown category {cid!r}")
        if not isinstance(w, int) or not 0 <= w <= MAX_WEIGHT:
            raise RankingError(f"weight for {cid!r} must be a whole number 0–{MAX_WEIGHT}")
        out[cid] = w
    if not any(out.values()):
        raise RankingError("at least one category needs a weight above 0")
    return out


def overall_score(scores: Mapping[str, CategoryScore], weights: Mapping[str, int]) -> float:
    pairs = [
        (scores[c].score, w) for c, w in weights.items() if w > 0 and scores[c].score is not None
    ]
    total = sum(w for _, w in pairs)
    return sum(s * w for s, w in pairs) / total if total else 0.0


def tier_for(rank: int, n: int) -> Tier:
    cut = math.ceil(TIER_SHARE * n)
    if rank <= cut:
        return "best"
    if rank > n - cut:
        return "worst"
    return "middle"


def rank_areas(
    bundle: NeighbourhoodBundle,
    category: str = OVERALL,
    weights: Mapping[str, int] | None = None,
) -> list[Ranked]:
    """All areas ranked by one category, or by the weighted overall score."""
    table = category_table(bundle)
    if category == OVERALL:
        w = validate_weights(weights)
        scores = {k: overall_score(v, w) for k, v in table.items()}
    elif category in CATEGORIES_BY_ID:
        if weights:
            raise RankingError("weights only apply to the overall ranking")
        scores = {k: v[category].score for k, v in table.items()}
        if any(s is None for s in scores.values()):
            raise RankingError(f"no data for {category!r} yet")
    else:
        raise RankingError(f"unknown category {category!r}")

    areas = sorted(bundle.regions, key=lambda a: (-round(scores[a.key], 1), a.name, a.key))
    n = len(areas)
    out: list[Ranked] = []
    prev: float | None = None
    rank = 0
    for i, a in enumerate(areas, start=1):
        s = round(scores[a.key], 1)
        if s != prev:
            rank, prev = i, s
        out.append(Ranked(a, rank, scores[a.key], tier_for(rank, n)))
    return out


def ranks_by_category(bundle: NeighbourhoodBundle) -> dict[str, dict[str, Ranked]]:
    """category id -> area key -> Ranked (for an area's detail view). Cached per bundle."""
    cached = bundle.__dict__.get("_ranks_by_category")
    if cached is None:
        cached = {
            c.id: {r.area.key: r for r in rank_areas(bundle, c.id)}
            for c in CATEGORIES
            if all(s[c.id].score is not None for s in category_table(bundle).values())
        }
        bundle.__dict__["_ranks_by_category"] = cached
    return cached
