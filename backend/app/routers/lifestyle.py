"""/lifestyle — Lifestyle Match API (T7.3; ADR-0010, ADR-0011, ADR-0012).

    GET  /lifestyle/catalog          questionnaire, presets, attributes, destinations, sources
    GET  /lifestyle/regions.geojson  simplified region outlines for the results map
    POST /lifestyle/profile          answers → weights (with reasons) + persona + summary
    POST /lifestyle/match            answers (+ weight overrides, exclusions) → ranked regions
    POST /lifestyle/listings         region + budget → WohnIQ listings inside that region

Privacy by design (ADR-0012):
  * Stateless: nothing a user sends is stored — no database writes, no cache, no session.
    /profile and /match don't touch the database at all (no repository dependency).
  * Never logged: request bodies and answer values are not written to any log; the
    only log lines are counts and timings. Answers travel in POST bodies, never in URLs,
    so access logs can't capture them either.
  * Bounded input: `Answers` accepts fixed choices only and rejects unknown fields;
    destinations are ids from a fixed list, so no address reaches us or a third party.
  * POST responses are `Cache-Control: no-store`.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.repository import ListingRepository, get_repository
from app.routers.search import ListingOut, RiskOut, _to_listing_out, _to_risk_out
from core.logging import get_logger
from lifestyle.attributes import ATTRIBUTES
from lifestyle.explain import explain_match
from lifestyle.persona import predict_persona
from lifestyle.profiles import ProfileBundle, get_bundle
from lifestyle.questionnaire import PAGES, PRESETS, QUESTIONS, Answers
from lifestyle.scoring import MatchError, RegionMatch, match, unscored_attributes
from lifestyle.shapes import get_shapes
from lifestyle.weights import Weights, apply_overrides, derive_weights

logger = get_logger(__name__)
router = APIRouter(prefix="/lifestyle", tags=["lifestyle"])

NO_STORE = {"Cache-Control": "no-store"}
CACHEABLE = "public, max-age=3600"


# --- Response models ------------------------------------------------------------------


class OptionOut(BaseModel):
    id: str
    label: str
    hint: str | None = None
    sets: dict[str, int]  # attribute -> level this option sets (transparency)


class QuestionOut(BaseModel):
    id: str
    page: str
    prompt: str
    help: str | None = None
    multi: bool
    max_choices: int
    options: list[OptionOut]


class PageOut(BaseModel):
    id: str
    title: str
    subtitle: str
    questions: list[str]


class PresetOut(BaseModel):
    id: str
    label: str
    blurb: str
    answers: Answers


class AttributeOut(BaseModel):
    id: str
    label: str
    description: str
    kind: str
    available: bool


class DestinationOut(BaseModel):
    id: str
    name: str
    short: str
    kind: str


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
    pages: list[PageOut]
    questions: list[QuestionOut]
    presets: list[PresetOut]
    attributes: list[AttributeOut]
    destinations: list[DestinationOut]
    sources: list[SourceOut]
    city: dict[str, dict]  # Berlin-wide reference figures (student room price etc.)
    region_count: int
    privacy: str


class WeightOut(BaseModel):
    attribute: str
    label: str
    value: int
    reasons: list[str]
    overridden: bool


class PersonaOut(BaseModel):
    id: str
    title: str
    emoji: str
    tagline: str
    priorities: list[str]
    summary: str
    disclaimer: str


class ChoiceOut(BaseModel):
    question: str
    answer: str


class ProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: Answers
    weights: dict[str, int] | None = None  # user overrides, attribute -> 0..5


class ProfileOut(BaseModel):
    persona: PersonaOut
    weights: list[WeightOut]
    choices: list[ChoiceOut]  # "here's what you told us"
    unscored: dict[str, str]


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: Answers
    weights: dict[str, int] | None = None
    excluded: list[str] = Field(default_factory=list, max_length=143)
    limit: int = Field(default=10, ge=1, le=143)


class CommuteOut(BaseModel):
    destination: str
    minutes: int
    changes: int | None = None
    estimated: bool  # straight-line fallback rather than a timetable route


class EvidenceOut(BaseModel):
    attribute: str
    label: str
    text: str
    source_id: str
    score: float
    weight: int


class FactorOut(BaseModel):
    attribute: str
    label: str
    weight: int
    score: float
    contribution: float
    raw: float
    unit: str
    berlin: float | None = None
    source_id: str
    year: str


class RegionResultOut(BaseModel):
    rank: int
    key: str
    name: str
    district: str
    score: int  # 0..100
    fits_budget: bool
    warm_rent_eur: int
    within_commute: bool | None
    commute: CommuteOut | None
    centroid: tuple[float, float] | None
    population: int
    headline: str
    reasons: list[EvidenceOut]
    caveats: list[str]  # trade-offs of this area for this user
    notes: list[str]  # caveats about the data (shown with "the data behind this")
    evidence: list[EvidenceOut]
    factors: list[FactorOut]


class RegionScoreOut(BaseModel):
    """Compact score for every ranked region (the results map shades all of them)."""

    key: str
    rank: int
    score: int
    fits_budget: bool
    within_commute: bool | None


class MatchOut(BaseModel):
    persona: PersonaOut
    weights: list[WeightOut]
    results: list[RegionResultOut]  # full detail for the top `limit`
    scores: list[RegionScoreOut]  # every ranked region, compact
    unscored: dict[str, str]
    excluded: list[str]
    total_regions: int


class ListingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    region_key: str = Field(pattern=r"^\d{6}$")
    budget_eur: int | None = Field(default=None, ge=200, le=10_000)
    min_rooms: float | None = Field(default=None, ge=1, le=8)
    limit: int = Field(default=12, ge=1, le=50)


class RegionListingOut(BaseModel):
    listing: ListingOut
    fits_budget: bool | None
    risk: RiskOut | None = None


class ListingsOut(BaseModel):
    region_key: str
    region_name: str
    count: int  # listings in the region matching min_rooms (before `limit`)
    listings: list[RegionListingOut]


# --- Helpers ------------------------------------------------------------------------------


def _weights(answers: Answers, overrides: dict[str, int] | None) -> Weights:
    try:
        return apply_overrides(derive_weights(answers), overrides)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _weights_out(weights: Weights) -> list[WeightOut]:
    labels = {a.id: a.label for a in ATTRIBUTES}
    return [
        WeightOut(
            attribute=a.id,
            label=labels[a.id],
            value=weights.value(a.id),
            reasons=list(weights.items[a.id].reasons) if a.id in weights.items else [],
            overridden=weights.items[a.id].overridden if a.id in weights.items else False,
        )
        for a in ATTRIBUTES
    ]


def _persona_out(bundle: ProfileBundle, answers: Answers, weights: Weights) -> PersonaOut:
    p = predict_persona(bundle, answers, weights.active())
    return PersonaOut(**vars(p))


def _choices(bundle: ProfileBundle, answers: Answers) -> list[ChoiceOut]:
    out = [
        ChoiceOut(question="Budget (warm)", answer=f"€{answers.budget_eur:,} per month"),
        ChoiceOut(
            question="Flat",
            answer=f"{answers.size_m2} m², {answers.rooms:g} "
            f"room{'' if answers.rooms == 1 else 's'}",
        ),
    ]
    if answers.destination:
        dest = bundle.destination(answers.destination)
        name = dest.name if dest else answers.destination
        out.append(
            ChoiceOut(
                question="Where you go most",
                answer=f"{name} (max. {answers.max_commute_min} min)",
            )
        )
    grouped: dict[str, list[str]] = {}
    for question, option in answers.chosen():
        grouped.setdefault(question.prompt, []).append(option.label)
    out += [ChoiceOut(question=q, answer=", ".join(labels)) for q, labels in grouped.items()]
    return out


def _region_out(m: RegionMatch, bundle: ProfileBundle, answers: Answers) -> RegionResultOut:
    e = explain_match(m, bundle, answers)

    def ev(x) -> EvidenceOut:
        return EvidenceOut(
            attribute=x.attribute,
            label=x.label,
            text=x.text,
            source_id=x.source_id,
            score=round(x.score, 3),
            weight=x.weight,
        )

    commute = None
    if m.commute is not None and answers.destination:
        commute = CommuteOut(
            destination=answers.destination,
            minutes=m.commute.minutes,
            changes=m.commute.changes,
            estimated=m.commute.source != "network",
        )
    return RegionResultOut(
        rank=m.rank,
        key=m.region.key,
        name=m.region.name,
        district=m.region.district,
        score=round(m.total * 100),
        fits_budget=m.fits_budget,
        warm_rent_eur=m.warm_rent_eur,
        within_commute=m.within_commute,
        commute=commute,
        centroid=m.region.centroid,
        population=m.region.population,
        headline=e.headline,
        reasons=[ev(x) for x in e.reasons],
        caveats=e.caveats,
        notes=e.notes,
        evidence=[ev(x) for x in e.evidence],
        factors=[
            FactorOut(
                attribute=f.attribute,
                label=f.label,
                weight=f.weight,
                score=round(f.score, 3),
                contribution=round(f.contribution, 4),
                raw=f.raw,
                unit=f.unit,
                berlin=f.berlin,
                source_id=f.source_id,
                year=f.year,
            )
            for f in m.factors
        ],
    )


# --- Endpoints ----------------------------------------------------------------------------


@router.get("/catalog", response_model=CatalogOut)
def catalog(response: Response) -> CatalogOut:
    """Everything the questionnaire UI needs. Static; contains no user data."""
    bundle = get_bundle()
    response.headers["Cache-Control"] = CACHEABLE
    available = {a.id for a in bundle.available_attributes()} | {"affordability"}
    if bundle.commute is not None:
        available.add("commute")
    return CatalogOut(
        pages=[
            PageOut(
                id=pid,
                title=title,
                subtitle=subtitle,
                questions=[q.id for q in QUESTIONS if q.page == pid],
            )
            for pid, title, subtitle in PAGES
        ],
        questions=[
            QuestionOut(
                id=q.id,
                page=q.page,
                prompt=q.prompt,
                help=q.help,
                multi=q.multi,
                max_choices=q.max_choices,
                options=[
                    OptionOut(id=o.id, label=o.label, hint=o.hint, sets=dict(o.weights))
                    for o in q.options
                ],
            )
            for q in QUESTIONS
        ],
        presets=[
            PresetOut(id=p.id, label=p.label, blurb=p.blurb, answers=p.answers) for p in PRESETS
        ],
        attributes=[
            AttributeOut(
                id=a.id,
                label=a.label,
                description=a.description,
                kind=a.kind,
                available=a.id in available,
            )
            for a in ATTRIBUTES
        ],
        destinations=[
            DestinationOut(id=d.id, name=d.name, short=d.short, kind=d.kind)
            for d in bundle.destinations
        ],
        sources=[SourceOut(**s.model_dump()) for s in bundle.sources.values()],
        city={k: v.model_dump() for k, v in bundle.city.items()},
        region_count=len(bundle.regions),
        privacy="Your answers are used only to compute this result. They are not stored "
        "or logged, and they never leave WohnIQ.",
    )


@router.get("/regions.geojson")
def regions_geojson(response: Response) -> dict:
    """Simplified region outlines (GeoJSON) for the results map. Static."""
    response.headers["Cache-Control"] = CACHEABLE
    return get_shapes().geojson


@router.post("/profile", response_model=ProfileOut)
def profile(req: ProfileRequest, response: Response) -> ProfileOut:
    """Answers → weights + persona, for the "Did we get this right?" step. Stateless."""
    response.headers.update(NO_STORE)
    bundle = get_bundle()
    weights = _weights(req.answers, req.weights)
    return ProfileOut(
        persona=_persona_out(bundle, req.answers, weights),
        weights=_weights_out(weights),
        choices=_choices(bundle, req.answers),
        unscored=unscored_attributes(bundle, req.answers, weights.active()),
    )


@router.post("/match", response_model=MatchOut)
def match_regions(req: MatchRequest, response: Response) -> MatchOut:
    """Rank Berlin's regions for these answers/weights. Stateless; nothing is stored."""
    response.headers.update(NO_STORE)
    started = time.perf_counter()
    bundle = get_bundle()
    weights = _weights(req.answers, req.weights)
    try:
        result = match(bundle, req.answers, weights, excluded=req.excluded)
    except MatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    out = MatchOut(
        persona=_persona_out(bundle, req.answers, weights),
        weights=_weights_out(weights),
        results=[_region_out(m, bundle, req.answers) for m in result.results[: req.limit]],
        scores=[
            RegionScoreOut(
                key=m.region.key,
                rank=m.rank,
                score=round(m.total * 100),
                fits_budget=m.fits_budget,
                within_commute=m.within_commute,
            )
            for m in result.results
        ],
        unscored=result.unscored,
        excluded=result.excluded,
        total_regions=len(bundle.regions),
    )
    # Counts and timing only — never answer values (ADR-0012).
    logger.info(
        "lifestyle match results=%d latency_ms=%d",
        len(out.results),
        round((time.perf_counter() - started) * 1000),
    )
    return out


@router.post("/listings", response_model=ListingsOut)
def region_listings(
    req: ListingsRequest,
    response: Response,
    repo: ListingRepository = Depends(get_repository),  # noqa: B008 (FastAPI idiom)
) -> ListingsOut:
    """WohnIQ listings whose coordinates lie inside the region (read-only)."""
    response.headers.update(NO_STORE)
    bundle = get_bundle()
    region = bundle.region(req.region_key)
    shapes = get_shapes()
    if region is None or req.region_key not in shapes:
        raise HTTPException(status_code=404, detail="Unknown region")
    shape = shapes.shapes[req.region_key]
    min_lng, min_lat, max_lng, max_lat = shape.bbox
    candidates = repo.listings_in_bbox(min_lat, min_lng, max_lat, max_lng)
    inside = [
        x
        for x in candidates
        if shape.contains(x.lat, x.lng) and (req.min_rooms is None or x.rooms >= req.min_rooms)
    ]

    def fits(x) -> bool | None:
        return None if req.budget_eur is None else x.warmmiete_eur <= req.budget_eur

    inside.sort(key=lambda x: (fits(x) is False, x.warmmiete_eur, str(x.id)))
    page = inside[: req.limit]
    photos = repo.photos_by_set([x.photo_set_id for x in page])
    risk = repo.risk_by_listing([x.id for x in page])
    return ListingsOut(
        region_key=region.key,
        region_name=region.name,
        count=len(inside),
        listings=[
            RegionListingOut(
                listing=_to_listing_out(x, photos.get(x.photo_set_id, [])),
                fits_budget=fits(x),
                risk=_to_risk_out(risk.get(str(x.id))),
            )
            for x in page
        ],
    )
