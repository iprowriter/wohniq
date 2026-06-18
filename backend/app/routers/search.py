"""/search — the end-to-end pipeline (T2.8 + T4.3): parse → retrieve → rank → explain,
now enriched with commute (F5) and neighborhood (F6).

Enrichment strategy (enrich top-k): rank the candidate pool on the cheap factors first
(relevance, budget, quiet-from-Kiez), take the page, then enrich *only* those listings
with commute + neighborhood and re-rank — so we don't pay ~20 Overpass/transit lookups
per search for listings we'll never show. (Neighborhood lookups can be pre-warmed into
the cache; commute is per-query but cached per origin+destination.)

`is_scam`/`scam_type` are NEVER serialized (AGENTS rule).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.db import get_session
from core.logging import get_logger
from data.kieze import KIEZE
from data.models import Listing, Photo, RiskAssessment
from enrich.commute import get_commute
from enrich.neighborhood import get_neighborhood
from search.criteria import SearchCriteria
from search.explanation import Explanation, explain
from search.parser import parse_query
from search.ranking import RankCriteria, RankingInput, rank, score_listing
from search.retrieval import retrieve

logger = get_logger(__name__)
router = APIRouter(tags=["search"])

_NIGHTLIFE = {k.name: k.nightlife for k in KIEZE}


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=6, ge=1, le=20)


class PhotoOut(BaseModel):
    url: str
    room_type: str
    attribution: str | None = None


class FactorOut(BaseModel):
    name: str
    score: float
    weight: float
    detail: str


class CommuteOut(BaseModel):
    minutes: int
    changes: int
    walk_minutes: int | None = None


class NeighborhoodOut(BaseModel):
    summary: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)


class RiskSignalOut(BaseModel):
    name: str
    source: str
    evidence: str
    severity: float


class RiskOut(BaseModel):
    band: str  # low | caution | high
    score: int
    signals: list[RiskSignalOut] = Field(default_factory=list)


class ListingOut(BaseModel):
    id: str
    title: str
    address: str
    kiez: str
    district: str | None
    rooms: float
    size_m2: int
    kaltmiete_eur: int
    nebenkosten_eur: int
    warmmiete_eur: int
    deposit_eur: int | None
    furnished: bool
    available_from: date | None
    photos: list[PhotoOut] = Field(default_factory=list)


class SearchResultItem(BaseModel):
    listing: ListingOut
    score: float
    factors: list[FactorOut]
    explanation: Explanation
    commute: CommuteOut | None = None
    neighborhood: NeighborhoodOut | None = None
    risk: RiskOut | None = None


class SearchResponse(BaseModel):
    criteria: SearchCriteria
    results: list[SearchResultItem]


def _load_photos(session: Session, set_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Photo]]:
    if not set_ids:
        return {}
    rows = session.scalars(
        select(Photo).where(Photo.photo_set_id.in_(set_ids)).order_by(Photo.position)
    )
    by_set: dict[uuid.UUID, list[Photo]] = {}
    for photo in rows:
        by_set.setdefault(photo.photo_set_id, []).append(photo)
    return by_set


def _load_risk(session: Session, listing_ids: list[uuid.UUID]) -> dict[str, RiskAssessment]:
    if not listing_ids:
        return {}
    rows = session.scalars(
        select(RiskAssessment).where(RiskAssessment.listing_id.in_(listing_ids))
    )
    return {str(r.listing_id): r for r in rows}


def _to_risk_out(row: RiskAssessment | None) -> RiskOut | None:
    if row is None:
        return None
    signals = [
        RiskSignalOut(
            name=s.get("name", ""),
            source=s.get("source", ""),
            evidence=s.get("evidence", ""),
            severity=float(s.get("severity", 0.0)),
        )
        for s in (row.signals or [])
    ]
    return RiskOut(band=row.band, score=row.score, signals=signals)


def _to_listing_out(listing: Listing, photos: list[Photo]) -> ListingOut:
    # NOTE: is_scam / scam_type are intentionally omitted — they never leave the server.
    return ListingOut(
        id=str(listing.id),
        title=listing.title,
        address=listing.address,
        kiez=listing.kiez,
        district=listing.district,
        rooms=float(listing.rooms),
        size_m2=listing.size_m2,
        kaltmiete_eur=listing.kaltmiete_eur,
        nebenkosten_eur=listing.nebenkosten_eur,
        warmmiete_eur=listing.warmmiete_eur,
        deposit_eur=listing.deposit_eur,
        furnished=listing.furnished,
        available_from=listing.available_from,
        photos=[
            PhotoOut(url=p.source_url, room_type=p.room_type, attribution=p.attribution)
            for p in photos
        ],
    )


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, session: Session = Depends(get_session)) -> SearchResponse:
    criteria = parse_query(req.query)
    rank_criteria = RankCriteria(
        max_warm_rent=criteria.max_warm_rent,
        quiet_priority=criteria.quiet_priority,
        desired_amenities=tuple(criteria.desired_amenities),
    )

    pool = retrieve(session, criteria, req.query, limit=max(req.limit * 3, 20))
    listings_by_id = {str(r.listing.id): r.listing for r in pool}
    distance_by_id = {str(r.listing.id): r.distance for r in pool}

    # Pass 1 — cheap factors (relevance, budget, quiet-from-Kiez) to pick the page.
    cheap_inputs = [
        RankingInput(
            warmmiete_eur=r.listing.warmmiete_eur,
            distance=r.distance,
            nightlife=_NIGHTLIFE.get(r.listing.kiez),
            listing_id=str(r.listing.id),
        )
        for r in pool
    ]
    page = rank(cheap_inputs, rank_criteria)[: req.limit]

    # Pass 2 — enrich just the page (commute + neighborhood), then re-rank.
    commute_by_id = {}
    neighborhood_by_id = {}
    enriched_inputs: list[RankingInput] = []
    for inp, _ in page:
        listing = listings_by_id[inp.listing_id]
        neighborhood = get_neighborhood(session, listing.lat, listing.lng)
        commute = get_commute(session, listing.lat, listing.lng, criteria.work_location)
        if neighborhood is not None:
            neighborhood_by_id[inp.listing_id] = neighborhood
        if commute is not None:
            commute_by_id[inp.listing_id] = commute
        enriched_inputs.append(
            RankingInput(
                warmmiete_eur=listing.warmmiete_eur,
                distance=distance_by_id[inp.listing_id],
                nightlife=_NIGHTLIFE.get(listing.kiez),
                available_amenities=neighborhood.available_amenities if neighborhood else None,
                commute_minutes=commute.minutes if commute else None,
                listing_id=inp.listing_id,
            )
        )
    ranked = rank(enriched_inputs, rank_criteria)

    page_listings = [listings_by_id[i.listing_id] for i, _ in ranked]
    photos_by_set = _load_photos(session, [x.photo_set_id for x in page_listings])
    risk_by_id = _load_risk(session, [x.id for x in page_listings])

    results: list[SearchResultItem] = []
    for inp, result in ranked:
        listing = listings_by_id[inp.listing_id]
        commute = commute_by_id.get(inp.listing_id)
        neighborhood = neighborhood_by_id.get(inp.listing_id)
        results.append(
            SearchResultItem(
                listing=_to_listing_out(listing, photos_by_set.get(listing.photo_set_id, [])),
                score=round(result.total, 4),
                factors=[FactorOut(**vars(f)) for f in result.factors],
                explanation=explain(result),
                risk=_to_risk_out(risk_by_id.get(inp.listing_id)),
                commute=(
                    CommuteOut(
                        minutes=commute.minutes,
                        changes=commute.changes,
                        walk_minutes=commute.walk_minutes,
                    )
                    if commute
                    else None
                ),
                neighborhood=(
                    NeighborhoodOut(summary=neighborhood.summary, counts=neighborhood.counts)
                    if neighborhood
                    else None
                ),
            )
        )

    logger.info(
        "search query=%r parsed=%s results=%d",
        req.query,
        criteria.model_dump(exclude_none=True),
        len(results),
    )
    return SearchResponse(criteria=criteria, results=results)


# --- Listing detail (T5.1) ------------------------------------------------------


class PoiOut(BaseModel):
    category: str
    name: str
    lat: float
    lng: float


class ListingDetailOut(BaseModel):
    id: str
    title: str
    description: str
    address: str
    kiez: str
    district: str | None
    lat: float
    lng: float
    rooms: float
    size_m2: int
    kaltmiete_eur: int
    nebenkosten_eur: int
    warmmiete_eur: int
    deposit_eur: int | None
    furnished: bool
    available_from: date | None
    floor: int | None
    total_floors: int | None
    anmeldung_possible: bool
    photos: list[PhotoOut] = Field(default_factory=list)


class NeighborhoodDetailOut(BaseModel):
    summary: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    pois: list[PoiOut] = Field(default_factory=list)


class ListingDetailResponse(BaseModel):
    listing: ListingDetailOut
    risk: RiskOut | None = None
    neighborhood: NeighborhoodDetailOut | None = None


@router.get("/listings/random", response_model=list[ListingOut])
def get_random_listings(n: int = 6, session: Session = Depends(get_session)) -> list[ListingOut]:
    rows = session.scalars(select(Listing).order_by(func.random()).limit(n)).all()
    if not rows:
        return []
    photos_by_set = _load_photos(session, [x.photo_set_id for x in rows])
    return [_to_listing_out(listing, photos_by_set.get(listing.photo_set_id, [])) for listing in rows]


@router.get("/listings/{listing_id}", response_model=ListingDetailResponse)
def get_listing(listing_id: str, session: Session = Depends(get_session)) -> ListingDetailResponse:
    try:
        uid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id") from None

    listing = session.get(Listing, uid)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    photos_by_set = _load_photos(session, [listing.photo_set_id])
    photos = photos_by_set.get(listing.photo_set_id, [])
    risk_by_id = _load_risk(session, [listing.id])
    neighborhood = get_neighborhood(session, listing.lat, listing.lng)

    neighborhood_detail: NeighborhoodDetailOut | None = None
    if neighborhood is not None:
        pois = [
            PoiOut(
                category=p.get("category", ""),
                name=p.get("name", ""),
                lat=float(p.get("lat", 0)),
                lng=float(p.get("lng", 0)),
            )
            for p in neighborhood.pois
        ]
        neighborhood_detail = NeighborhoodDetailOut(
            summary=neighborhood.summary,
            counts=neighborhood.counts,
            pois=pois,
        )

    return ListingDetailResponse(
        listing=ListingDetailOut(
            id=str(listing.id),
            title=listing.title,
            description=listing.description,
            address=listing.address,
            kiez=listing.kiez,
            district=listing.district,
            lat=listing.lat,
            lng=listing.lng,
            rooms=float(listing.rooms),
            size_m2=listing.size_m2,
            kaltmiete_eur=listing.kaltmiete_eur,
            nebenkosten_eur=listing.nebenkosten_eur,
            warmmiete_eur=listing.warmmiete_eur,
            deposit_eur=listing.deposit_eur,
            furnished=listing.furnished,
            available_from=listing.available_from,
            floor=listing.floor,
            total_floors=listing.total_floors,
            anmeldung_possible=listing.anmeldung_possible,
            photos=[
                PhotoOut(url=p.source_url, room_type=p.room_type, attribution=p.attribution)
                for p in photos
            ],
        ),
        risk=_to_risk_out(risk_by_id.get(str(listing.id))),
        neighborhood=neighborhood_detail,
    )


# --- Comparison (F8) ------------------------------------------------------------
# Side-by-side of 2–4 listings. Reuses the exact same helpers as /search
# (_to_listing_out, enrichment, score_listing, explain) so the compared fields can't
# drift from what search shows (SPEC F8 AC1).


class CompareRequest(BaseModel):
    listing_ids: list[str] = Field(min_length=2, max_length=4)
    query: str | None = None  # optional context for fit + commute


class ComparisonItem(BaseModel):
    listing: ListingOut
    fit_score: float | None = None
    factors: list[FactorOut] = Field(default_factory=list)
    explanation: Explanation | None = None
    commute: CommuteOut | None = None
    neighborhood: NeighborhoodOut | None = None
    risk: RiskOut | None = None


class CompareResponse(BaseModel):
    criteria: SearchCriteria | None = None
    items: list[ComparisonItem]


@router.post("/compare", response_model=CompareResponse)
def compare(req: CompareRequest, session: Session = Depends(get_session)) -> CompareResponse:
    try:
        ids = [uuid.UUID(x) for x in req.listing_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id") from None

    found = {str(x.id): x for x in session.scalars(select(Listing).where(Listing.id.in_(ids)))}
    missing = [x for x in req.listing_ids if x not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Listing(s) not found: {missing}")
    ordered = [found[x] for x in req.listing_ids]  # preserve requested order

    criteria = parse_query(req.query) if req.query else None
    rank_criteria = (
        RankCriteria(
            max_warm_rent=criteria.max_warm_rent,
            quiet_priority=criteria.quiet_priority,
            desired_amenities=tuple(criteria.desired_amenities),
        )
        if criteria
        else None
    )
    photos_by_set = _load_photos(session, [x.photo_set_id for x in ordered])
    risk_by_id = _load_risk(session, [x.id for x in ordered])

    items: list[ComparisonItem] = []
    for listing in ordered:
        neighborhood = get_neighborhood(session, listing.lat, listing.lng)
        commute = (
            get_commute(session, listing.lat, listing.lng, criteria.work_location)
            if criteria
            else None
        )

        fit_score: float | None = None
        factors: list[FactorOut] = []
        explanation: Explanation | None = None
        if rank_criteria is not None:
            result = score_listing(
                RankingInput(
                    warmmiete_eur=listing.warmmiete_eur,
                    distance=0.0,  # no per-listing query vector here; relevance is constant
                    nightlife=_NIGHTLIFE.get(listing.kiez),
                    available_amenities=neighborhood.available_amenities if neighborhood else None,
                    commute_minutes=commute.minutes if commute else None,
                    listing_id=str(listing.id),
                ),
                rank_criteria,
            )
            fit_score = round(result.total, 4)
            factors = [FactorOut(**vars(f)) for f in result.factors]
            explanation = explain(result)

        items.append(
            ComparisonItem(
                listing=_to_listing_out(listing, photos_by_set.get(listing.photo_set_id, [])),
                fit_score=fit_score,
                factors=factors,
                explanation=explanation,
                commute=(
                    CommuteOut(
                        minutes=commute.minutes,
                        changes=commute.changes,
                        walk_minutes=commute.walk_minutes,
                    )
                    if commute
                    else None
                ),
                neighborhood=(
                    NeighborhoodOut(summary=neighborhood.summary, counts=neighborhood.counts)
                    if neighborhood
                    else None
                ),
                risk=_to_risk_out(risk_by_id.get(str(listing.id))),
            )
        )

    return CompareResponse(criteria=criteria, items=items)
