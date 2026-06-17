"""/search — the end-to-end pipeline (T2.8): parse → retrieve → rank → explain.

Wires the M2 spine behind one endpoint. The response carries the parsed criteria
(so the UI can show "Understood as …"), and per result the listing, the score, the
factor breakdown, and the grounded explanation.

Two deliberate notes:
- `is_scam`/`scam_type` are NEVER serialized (ground-truth labels, AGENTS rule).
- Commute and neighborhood-amenity factors arrive with M4; for now ranking uses
  relevance + budget + quiet (nightlife comes from static Kiez data, no API).
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import get_session
from core.logging import get_logger
from data.kieze import KIEZE
from data.models import Listing, Photo
from search.criteria import SearchCriteria
from search.explanation import Explanation, explain
from search.parser import parse_query
from search.ranking import RankCriteria, RankingInput, rank
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

    # Retrieve a candidate pool larger than the page we return, then rank.
    pool = retrieve(session, criteria, req.query, limit=max(req.limit * 3, 20))
    listings_by_id = {str(r.listing.id): r.listing for r in pool}

    inputs = [
        RankingInput(
            warmmiete_eur=r.listing.warmmiete_eur,
            distance=r.distance,
            nightlife=_NIGHTLIFE.get(r.listing.kiez),
            listing_id=str(r.listing.id),
        )
        for r in pool
    ]
    rank_criteria = RankCriteria(
        max_warm_rent=criteria.max_warm_rent,
        quiet_priority=criteria.quiet_priority,
        desired_amenities=tuple(criteria.desired_amenities),
    )
    ranked = rank(inputs, rank_criteria)[: req.limit]

    photos_by_set = _load_photos(
        session, [listings_by_id[i.listing_id].photo_set_id for i, _ in ranked]
    )

    results: list[SearchResultItem] = []
    for inp, result in ranked:
        listing = listings_by_id[inp.listing_id]
        results.append(
            SearchResultItem(
                listing=_to_listing_out(listing, photos_by_set.get(listing.photo_set_id, [])),
                score=round(result.total, 4),
                factors=[FactorOut(**vars(f)) for f in result.factors],
                explanation=explain(result),
            )
        )

    logger.info(
        "search query=%r parsed=%s results=%d",
        req.query,
        criteria.model_dump(exclude_none=True),
        len(results),
    )
    return SearchResponse(criteria=criteria, results=results)
