"""Retrieval (F2): turn SearchCriteria + the raw query into a candidate shortlist.

Two stages, two tools (the design point of T2.4):
  * Hard constraints (budget, rooms, size) become SQL WHERE filters — exact, non-
    negotiable. A listing over budget is excluded, not down-weighted.
  * The fuzzy "vibe" of the request is matched semantically: we embed the raw query
    and order survivors by cosine distance to each listing's embedding (pgvector,
    HNSW index).

The vector comparison uses pgvector's typed `cosine_distance` expression so the
768-dim query vector is bound safely — clearer and safer than interpolating it into
raw SQL. Ordering/scoring beyond this shortlist is the ranker's job (T2.5), not here.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.embeddings import embed_query
from data.models import Listing, ListingEmbedding
from search.criteria import SearchCriteria
from search.filters import build_hard_filters

_COLUMNS = {
    "warmmiete_eur": Listing.warmmiete_eur,
    "rooms": Listing.rooms,
    "size_m2": Listing.size_m2,
}
_OPS = {"<=": operator.le, ">=": operator.ge}


@dataclass
class RetrievalResult:
    listing: Listing
    distance: float  # cosine distance to the query; smaller = more relevant


def retrieve(
    session: Session,
    criteria: SearchCriteria,
    query_text: str,
    *,
    limit: int = 20,
    embedder: Callable[[str], list[float]] | None = None,
) -> list[RetrievalResult]:
    """Return up to `limit` candidate listings, hard-filtered and semantically ranked."""
    embed = embedder or embed_query
    query_vector = embed(query_text)

    distance = ListingEmbedding.embedding.cosine_distance(query_vector).label("distance")
    stmt = select(Listing, distance).join(
        ListingEmbedding, ListingEmbedding.listing_id == Listing.id
    )
    for column, op, value in build_hard_filters(
        criteria.max_warm_rent, criteria.min_rooms, criteria.min_size_m2
    ):
        stmt = stmt.where(_OPS[op](_COLUMNS[column], value))
    stmt = stmt.order_by(distance).limit(limit)

    return [RetrievalResult(listing=row[0], distance=row[1]) for row in session.execute(stmt)]
