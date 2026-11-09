"""Data-access seam for the API routers: live Postgres or the offline demo fixtures.

The routers own the pipeline (parse → retrieve → rank → explain); a repository only
answers "give me listings / photos / risk / enrichment". Two implementations:

  * SqlRepository  — Supabase Postgres + pgvector, live Overpass/VBB enrichment
                     (the production path; same queries the router used to inline).
  * DemoRepository — bundled JSON fixtures, no network at all (data/demo_repository.py).

`get_repository` picks one per request from `settings.demo_mode`, so the demo never
opens a DB connection and production never touches the fixtures.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.config import settings
from core.db import get_sessionmaker
from data.models import Listing, Photo, RiskAssessment
from enrich.commute import get_commute
from enrich.commute_parse import CommuteResult
from enrich.neighborhood import get_neighborhood
from enrich.neighborhood_parse import NeighborhoodResult
from search.criteria import SearchCriteria
from search.retrieval import RetrievalResult, retrieve


class ListingRepository(Protocol):
    def random_listings(self, n: int) -> list[Listing]: ...

    def get_listing(self, listing_id: uuid.UUID) -> Listing | None: ...

    def get_listings(self, listing_ids: Sequence[uuid.UUID]) -> list[Listing]: ...

    def listings_in_bbox(
        self, min_lat: float, min_lng: float, max_lat: float, max_lng: float, *, limit: int = 500
    ) -> list[Listing]: ...

    def retrieve(
        self, criteria: SearchCriteria, query_text: str, *, limit: int
    ) -> list[RetrievalResult]: ...

    def photos_by_set(self, set_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Photo]]: ...

    def risk_by_listing(self, listing_ids: Sequence[uuid.UUID]) -> dict[str, RiskAssessment]: ...

    def neighborhood(
        self, lat: float, lng: float, *, cache_only: bool = False
    ) -> NeighborhoodResult | None: ...

    def commute(
        self, lat: float, lng: float, work_location: str | None
    ) -> CommuteResult | None: ...


class SqlRepository:
    """Postgres-backed repository (production)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def random_listings(self, n: int) -> list[Listing]:
        return list(self.session.scalars(select(Listing).order_by(func.random()).limit(n)))

    def get_listing(self, listing_id: uuid.UUID) -> Listing | None:
        return self.session.get(Listing, listing_id)

    def get_listings(self, listing_ids: Sequence[uuid.UUID]) -> list[Listing]:
        return list(self.session.scalars(select(Listing).where(Listing.id.in_(listing_ids))))

    def listings_in_bbox(
        self, min_lat: float, min_lng: float, max_lat: float, max_lng: float, *, limit: int = 500
    ) -> list[Listing]:
        """Listings inside a lat/lng box (Lifestyle Match hand-off; exact region test follows)."""
        return list(
            self.session.scalars(
                select(Listing)
                .where(
                    Listing.lat.between(min_lat, max_lat),
                    Listing.lng.between(min_lng, max_lng),
                )
                .order_by(Listing.warmmiete_eur, Listing.id)
                .limit(limit)
            )
        )

    def retrieve(
        self, criteria: SearchCriteria, query_text: str, *, limit: int
    ) -> list[RetrievalResult]:
        return retrieve(self.session, criteria, query_text, limit=limit)

    def photos_by_set(self, set_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Photo]]:
        if not set_ids:
            return {}
        rows = self.session.scalars(
            select(Photo).where(Photo.photo_set_id.in_(set_ids)).order_by(Photo.position)
        )
        by_set: dict[uuid.UUID, list[Photo]] = {}
        for photo in rows:
            by_set.setdefault(photo.photo_set_id, []).append(photo)
        return by_set

    def risk_by_listing(self, listing_ids: Sequence[uuid.UUID]) -> dict[str, RiskAssessment]:
        if not listing_ids:
            return {}
        rows = self.session.scalars(
            select(RiskAssessment).where(RiskAssessment.listing_id.in_(listing_ids))
        )
        return {str(r.listing_id): r for r in rows}

    def neighborhood(
        self, lat: float, lng: float, *, cache_only: bool = False
    ) -> NeighborhoodResult | None:
        return get_neighborhood(self.session, lat, lng, cache_only=cache_only)

    def commute(self, lat: float, lng: float, work_location: str | None) -> CommuteResult | None:
        return get_commute(self.session, lat, lng, work_location)


def get_repository() -> Iterator[ListingRepository]:
    """FastAPI dependency: the demo fixtures in demo mode, otherwise a DB session."""
    if settings.demo_mode:
        from data.demo_repository import get_demo_repository

        yield get_demo_repository()
        return

    with get_sessionmaker()() as session:
        yield SqlRepository(session)
