"""/neighborhoods — Berlin Neighbourhoods API (M8; ADR-0013).

    GET /neighborhoods/catalog          categories, metrics (with Berlin figures), sources
    GET /neighborhoods/ranking          all 143 areas ranked by a category or overall
                                        (?category=safety | ?category=overall&weights=safety:3,…)
    GET /neighborhoods/areas/{key}      one area: every category and metric, with sources
    GET /neighborhoods/regions.geojson  simplified area outlines for the map

Read-only and deterministic: everything comes from the shipped bundle
(data/neighborhoods/neighborhoods.json). No database, no third-party calls, nothing
stored — so it works identically in offline demo mode. Requests carry no personal data
(a category and optional weights), so responses are cacheable.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from core.logging import get_logger
from lifestyle.shapes import get_shapes
from neighborhoods.bundle import NeighbourhoodBundle, get_bundle
from neighborhoods.catalog import CATEGORIES, MAX_WEIGHT, METRICS, OVERALL, Metric
from neighborhoods.explain import Highlight, format_value, headline_metric, highlights, summary
from neighborhoods.scoring import (
    RankingError,
    category_table,
    default_weights,
    rank_areas,
    ranks_by_category,
    validate_weights,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/neighborhoods", tags=["neighborhoods"])

CACHEABLE = "public, max-age=3600"
OVERALL_LABEL = "Overall"
CITY_FIGURE_FOR = {"income": "income_per_taxpayer"}  # metric id -> bundle.city figure id
OVERALL_DESCRIPTION = (
    "A weighted blend of every category. Adjust the weights to match what matters to you."
)


# --- Response models ------------------------------------------------------------------------


class MetricOut(BaseModel):
    id: str
    label: str
    unit: str
    higher_is_better: bool
    weight: float
    description: str
    level: str
    available: bool
    requires: str | None = None  # no per-area data: why
    berlin: float | None = None
    berlin_text: str | None = None
    berlin_method: str | None = None
    # A Berlin-wide figure for a metric we can't yet show per area (e.g. income).
    city_text: str | None = None
    city_note: str | None = None
    city_source_id: str | None = None


class CategoryOut(BaseModel):
    id: str
    label: str
    emoji: str
    question: str
    best_label: str
    worst_label: str
    default_weight: int
    caveat: str
    metrics: list[MetricOut]


class SourceOut(BaseModel):
    id: str
    title: str
    publisher: str
    url: str | None = None
    licence: str | None = None
    data_year: str
    used_for: str
    caveat: str | None = None


class CatalogOut(BaseModel):
    overall: dict[str, str]
    categories: list[CategoryOut]
    sources: list[SourceOut]
    area_count: int
    max_weight: int
    districts: list[str]


class HeadlineOut(BaseModel):
    metric: str
    label: str
    raw: float
    text: str  # formatted value + unit, e.g. "1,236 per 100,000 residents"


class RankedAreaOut(BaseModel):
    key: str
    name: str
    district: str
    area_group: str
    rank: int
    score: float  # 0–100, one decimal
    tier: str  # best | middle | worst
    centroid: tuple[float, float]
    headline: HeadlineOut | None = None  # the category's key figure (None for overall)


class RankingOut(BaseModel):
    category: str
    label: str
    best_label: str | None
    worst_label: str | None
    weights: dict[str, int] | None  # effective weights (overall only)
    total: int
    areas: list[RankedAreaOut]


class HighlightOut(BaseModel):
    category: str
    label: str
    rank: int
    text: str
    source_id: str


class MetricValueOut(BaseModel):
    id: str
    label: str
    unit: str
    raw: float
    text: str  # value as users read it
    berlin_text: str
    score: float  # 0–100 percentile
    weight: float
    higher_is_better: bool
    level: str
    source_id: str
    year: str
    method: str
    count: int | None = None
    shares: dict[str, float] | None = None


class CategoryDetailOut(BaseModel):
    id: str
    label: str
    emoji: str
    score: float
    rank: int
    tier: str
    tier_label: str | None
    metrics: list[MetricValueOut]


class AreaOut(BaseModel):
    key: str
    name: str
    district: str
    area_group: str
    population: int
    area_km2: float
    centroid: tuple[float, float]
    rent_range: tuple[float, float] | None
    overall: CategoryDetailOut
    summary: str
    strengths: list[HighlightOut]
    watch_outs: list[HighlightOut]
    categories: list[CategoryDetailOut]
    total: int


# --- Helpers ----------------------------------------------------------------------------------


def parse_weights(text: str | None) -> dict[str, int] | None:
    """ "safety:3,parking:0" → {"safety": 3, "parking": 0}; 422 on anything malformed."""
    if not text:
        return None
    out: dict[str, int] = {}
    for part in text.split(","):
        cid, sep, value = part.strip().partition(":")
        if not sep or not value.strip().isdigit():
            raise HTTPException(422, f"weights must look like 'safety:3,transit:1' (got {part!r})")
        out[cid.strip()] = int(value)
    try:
        return validate_weights(out)
    except RankingError as exc:
        raise HTTPException(422, str(exc)) from None


def _metric_out(bundle: NeighbourhoodBundle, m: Metric) -> MetricOut:
    ref = bundle.references.get(m.id)
    fig = bundle.city.get(CITY_FIGURE_FOR.get(m.id, ""))
    return MetricOut(
        id=m.id,
        label=m.label,
        unit=m.unit,
        higher_is_better=m.higher_is_better,
        weight=m.weight,
        description=m.description,
        level=m.level,
        available=ref is not None,
        requires=m.requires,
        berlin=ref.berlin if ref else None,
        berlin_text=format_value(m, ref.berlin) if ref else None,
        berlin_method=ref.berlin_method if ref else None,
        city_text=f"€{fig.value:,.0f} per taxpayer ({fig.year})" if fig else None,
        city_note=fig.note if fig else None,
        city_source_id=fig.source_id if fig else None,
    )


def _highlight_out(h: Highlight) -> HighlightOut:
    return HighlightOut(
        category=h.category, label=h.label, rank=h.rank, text=h.text, source_id=h.source_id
    )


def _headline(bundle: NeighbourhoodBundle, key: str, category_id: str) -> HeadlineOut:
    category = next(c for c in CATEGORIES if c.id == category_id)
    m = headline_metric(category)
    raw = bundle.area(key).values[m.id].raw  # type: ignore[union-attr]
    text = format_value(m, raw)
    if m.fmt not in ("metres", "minutes", "eur_m2", "pct"):
        text = f"{text} {m.unit}"
    return HeadlineOut(metric=m.id, label=m.label, raw=raw, text=text)


# --- Endpoints ----------------------------------------------------------------------------------


@router.get("/catalog", response_model=CatalogOut)
def catalog(response: Response) -> CatalogOut:
    """Everything the page needs to describe the categories. Static."""
    bundle = get_bundle()
    response.headers["Cache-Control"] = CACHEABLE
    return CatalogOut(
        overall={"id": OVERALL, "label": OVERALL_LABEL, "description": OVERALL_DESCRIPTION},
        categories=[
            CategoryOut(
                id=c.id,
                label=c.label,
                emoji=c.emoji,
                question=c.question,
                best_label=c.best_label,
                worst_label=c.worst_label,
                default_weight=c.default_weight,
                caveat=c.caveat,
                metrics=[_metric_out(bundle, m) for m in METRICS if m.category == c.id],
            )
            for c in CATEGORIES
        ],
        sources=[SourceOut(**s.model_dump()) for s in bundle.sources.values()],
        area_count=len(bundle.regions),
        max_weight=MAX_WEIGHT,
        districts=sorted({a.district for a in bundle.regions}),
    )


@router.get("/ranking", response_model=RankingOut)
def ranking(
    response: Response,
    category: str = Query(default=OVERALL, max_length=32),
    weights: str | None = Query(default=None, max_length=300),
) -> RankingOut:
    """All areas ranked Berlin-wide. Filtering the list (e.g. by district) is done by the
    client and never changes a rank."""
    start = time.perf_counter()
    bundle = get_bundle()
    parsed = parse_weights(weights)
    if parsed is not None and category != OVERALL:
        raise HTTPException(422, "weights only apply to the overall ranking")
    try:
        ranked = rank_areas(bundle, category, parsed)
    except RankingError as exc:
        raise HTTPException(422, str(exc)) from None
    cat = next((c for c in CATEGORIES if c.id == category), None)
    response.headers["Cache-Control"] = CACHEABLE
    out = RankingOut(
        category=category,
        label=cat.label if cat else OVERALL_LABEL,
        best_label=cat.best_label if cat else "Top 20% overall",
        worst_label=cat.worst_label if cat else "Bottom 20% overall",
        weights=(parsed or default_weights()) if category == OVERALL else None,
        total=len(ranked),
        areas=[
            RankedAreaOut(
                key=r.area.key,
                name=r.area.name,
                district=r.area.district,
                area_group=r.area.area_group,
                rank=r.rank,
                score=round(r.score, 1),
                tier=r.tier,
                centroid=r.area.centroid,
                headline=_headline(bundle, r.area.key, category) if cat else None,
            )
            for r in ranked
        ],
    )
    logger.info(
        "neighborhoods ranking: %d areas in %.0f ms",
        len(ranked),
        1000 * (time.perf_counter() - start),
    )
    return out


@router.get("/areas/{key}", response_model=AreaOut)
def area(
    key: str,
    response: Response,
    weights: str | None = Query(default=None, max_length=300),
) -> AreaOut:
    """One area in full: overall rank (with the given weights), every category and metric."""
    bundle = get_bundle()
    a = bundle.area(key)
    if a is None:
        raise HTTPException(404, f"unknown area {key!r}")
    parsed = parse_weights(weights)
    overall = next(r for r in rank_areas(bundle, OVERALL, parsed) if r.area.key == key)
    ranks = ranks_by_category(bundle)
    table = category_table(bundle)[key]
    strengths, watch = highlights(bundle, key)
    n = len(bundle.regions)

    def tier_label(tier: str, best: str, worst: str) -> str | None:
        return best if tier == "best" else worst if tier == "worst" else None

    categories = []
    for c in CATEGORIES:
        cs = table[c.id]
        r = ranks[c.id][key]
        categories.append(
            CategoryDetailOut(
                id=c.id,
                label=c.label,
                emoji=c.emoji,
                score=round(cs.score or 0.0, 1),
                rank=r.rank,
                tier=r.tier,
                tier_label=tier_label(r.tier, c.best_label, c.worst_label),
                metrics=[
                    MetricValueOut(
                        id=s.metric.id,
                        label=s.metric.label,
                        unit=s.metric.unit,
                        raw=s.value.raw,
                        text=format_value(s.metric, s.value.raw),
                        berlin_text=format_value(s.metric, s.berlin),
                        score=round(s.score, 1),
                        weight=s.metric.weight,
                        higher_is_better=s.metric.higher_is_better,
                        level=s.metric.level,
                        source_id=s.value.source_id,
                        year=s.value.year,
                        method=s.value.method,
                        count=s.value.count,
                        shares=s.value.shares,
                    )
                    for s in cs.metrics
                ],
            )
        )
    response.headers["Cache-Control"] = CACHEABLE
    return AreaOut(
        key=a.key,
        name=a.name,
        district=a.district,
        area_group=a.area_group,
        population=a.population,
        area_km2=a.area_km2,
        centroid=a.centroid,
        rent_range=a.rent_range,
        overall=CategoryDetailOut(
            id=OVERALL,
            label=OVERALL_LABEL,
            emoji="⭐",
            score=round(overall.score, 1),
            rank=overall.rank,
            tier=overall.tier,
            tier_label=tier_label(overall.tier, "Top 20% overall", "Bottom 20% overall"),
            metrics=[],
        ),
        summary=summary(bundle, key, overall.rank),
        strengths=[_highlight_out(h) for h in strengths],
        watch_outs=[_highlight_out(h) for h in watch],
        categories=categories,
        total=n,
    )


@router.get("/regions.geojson")
def regions_geojson(response: Response) -> dict:
    """Simplified outlines of the 143 areas (same file as Lifestyle Match)."""
    response.headers["Cache-Control"] = CACHEABLE
    return get_shapes().geojson
