"""Offline demo repository — serves the app from bundled fixtures, with zero network.

Sources (all local):
  * listings       — `generate_listings(seed=42)`, which reproduces the seeded DB rows
                     exactly (same ids, prices, photo sets); see export_demo_data.py.
  * photos.json    — photo rows. URLs point at a local copy under data/demo/photos/
                     when present (fetch once with `make demo-photos`), else at Pexels.
  * risk.json      — stored risk assessments (band, score, evidence).
  * neighborhoods.json — cached OSM POIs + counts + summary, keyed like the DB cache.

What offline mode can't do, and how it degrades:
  * Commute (live BVG/VBB) → an estimate from straight-line distance and published
    average speeds (enrich/commute_estimate.py, ADR-0008), flagged as estimated. Work
    locations resolve via the local place index (VBB stops + Kiez centres).
  * Semantic search (Gemini embeddings) → a lexical stand-in; see `_distance`.
  * Listings without a cached neighborhood → no amenities (as in prod, which reads
    the same cache). `random_listings` only picks listings that have one, so every
    featured card opens onto a complete detail page.
"""

from __future__ import annotations

import json
import operator
import random
import re
import uuid
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from core.logging import get_logger
from data.models import Listing, NeighborhoodCache, Photo, RiskAssessment
from data.synthetic import generate_listings
from enrich.commute import estimate_commute_to
from enrich.commute_parse import CommuteResult
from enrich.neighborhood import _from_cache, _location_key
from enrich.neighborhood_parse import NeighborhoodResult
from search.criteria import SearchCriteria
from search.filters import build_hard_filters
from search.retrieval import RetrievalResult

logger = get_logger(__name__)

DEMO_DIR = Path(__file__).parent / "demo"
PHOTOS_DIR = DEMO_DIR / "photos"
PHOTOS_URL_PREFIX = "/demo-photos"  # mounted by app.main in demo mode

# Must match how the live DB was seeded (data.seed_listings defaults).
DEMO_SEED = 42
DEMO_COUNT = 100

_OPS = {"<=": operator.le, ">=": operator.ge}
_WORD = re.compile(r"[a-zäöüß]+")
_STOPWORDS = set("""
    the and for with near nearby close around want looking need flat apartment budget good
    work not too area place something some that this from into under max ideally very
    """.split())


def local_photo_name(source_url: str) -> str:
    """Filename for a hotlinked photo's local copy (the URL's last path segment)."""
    return Path(urlparse(source_url).path).name


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) >= 3 and w not in _STOPWORDS}


def _listing_text(listing: Listing) -> str:
    # District is left out on purpose: "Friedrichshain-Kreuzberg" would make every
    # Friedrichshain flat match "Kreuzberg" (same for Mitte vs. Moabit/Wedding).
    return " ".join([listing.title, listing.description, listing.kiez])


def _distance(query_tokens: set[str], listing_tokens: set[str]) -> float:
    """Lexical stand-in for the embedding cosine distance (lower = more relevant).

    Without embeddings we score what fraction of the query's content words appear in
    the listing's title/description/Kiez. Relevance is mapped into [0.5, 1.0] so this
    always-on factor stays in the range real embeddings produce — it can lift a listing
    that names the requested Kiez, but can't sink every total into "partial match".
    """
    if not query_tokens:
        return 0.5
    overlap = len(query_tokens & listing_tokens) / len(query_tokens)
    return 0.5 * (1.0 - overlap)


def _load_json(name: str) -> list[dict]:
    return json.loads((DEMO_DIR / name).read_text(encoding="utf-8"))


def _to_listing(s) -> Listing:
    listing = Listing(
        id=s.id,
        title=s.title,
        description=s.description,
        address=s.address,
        kiez=s.kiez,
        district=s.district,
        lat=s.lat,
        lng=s.lng,
        rooms=s.rooms,
        size_m2=s.size_m2,
        kaltmiete_eur=s.kaltmiete_eur,
        nebenkosten_eur=s.nebenkosten_eur,
        deposit_eur=s.deposit_eur,
        furnished=s.furnished,
        available_from=s.available_from,
        floor=s.floor,
        total_floors=s.total_floors,
        anmeldung_possible=s.anmeldung_possible,
        photo_set_id=s.photo_set_id,
    )
    listing.warmmiete_eur = s.warmmiete_eur  # DB-computed in prod; same formula
    return listing


class DemoRepository:
    """In-memory, read-only implementation of app.repository.ListingRepository."""

    def __init__(self) -> None:
        listings = [_to_listing(s) for s in generate_listings(DEMO_COUNT, seed=DEMO_SEED)]
        self._listings: dict[uuid.UUID, Listing] = {x.id: x for x in listings}

        self._photos: dict[uuid.UUID, list[dict]] = {}
        for row in sorted(_load_json("photos.json"), key=lambda r: r["position"]):
            self._photos.setdefault(uuid.UUID(row["photo_set_id"]), []).append(row)

        self._risk: dict[str, RiskAssessment] = {
            row["listing_id"]: RiskAssessment(
                listing_id=uuid.UUID(row["listing_id"]),
                score=row["score"],
                band=row["band"],
                signals=row["signals"],
            )
            for row in _load_json("risk.json")
        }

        self._neighborhoods: dict[str, NeighborhoodResult] = {
            row["location_key"]: _from_cache(
                NeighborhoodCache(
                    location_key=row["location_key"],
                    poi_counts=row["poi_counts"],
                    pois=row["pois"],
                    summary=row["summary"],
                )
            )
            for row in _load_json("neighborhoods.json")
        }

        self._tokens = {x.id: _tokens(_listing_text(x)) for x in listings}
        self._featured = [
            x for x in listings if _location_key(x.lat, x.lng) in self._neighborhoods
        ] or listings
        self._check_fixtures()
        logger.info(
            "demo data: %d listings (%d with neighborhood data), %d photo sets, %d risk rows",
            len(self._listings),
            len(self._featured),
            len(self._photos),
            len(self._risk),
        )

    def _check_fixtures(self) -> None:
        """Fail loudly if the generator and the exported fixtures have drifted apart."""
        no_photos = [x for x in self._listings.values() if x.photo_set_id not in self._photos]
        no_risk = [x for x in self._listings.values() if str(x.id) not in self._risk]
        if no_photos or no_risk:
            raise RuntimeError(
                f"Demo fixtures don't match data.synthetic (seed={DEMO_SEED}): "
                f"{len(no_photos)} listings without photos, {len(no_risk)} without risk. "
                "Re-export with `uv run python -m data.export_demo_data`."
            )

    # --- ListingRepository -------------------------------------------------------

    def random_listings(self, n: int) -> list[Listing]:
        return random.sample(self._featured, k=min(max(n, 0), len(self._featured)))

    def get_listing(self, listing_id: uuid.UUID) -> Listing | None:
        return self._listings.get(listing_id)

    def get_listings(self, listing_ids: Sequence[uuid.UUID]) -> list[Listing]:
        return [self._listings[i] for i in listing_ids if i in self._listings]

    def listings_in_bbox(
        self, min_lat: float, min_lng: float, max_lat: float, max_lng: float, *, limit: int = 500
    ) -> list[Listing]:
        inside = [
            x
            for x in self._listings.values()
            if min_lat <= x.lat <= max_lat and min_lng <= x.lng <= max_lng
        ]
        return sorted(inside, key=lambda x: (x.warmmiete_eur, str(x.id)))[:limit]

    def retrieve(
        self, criteria: SearchCriteria, query_text: str, *, limit: int
    ) -> list[RetrievalResult]:
        filters = build_hard_filters(
            criteria.max_warm_rent, criteria.min_rooms, criteria.min_size_m2
        )
        query_tokens = _tokens(query_text)
        results = [
            RetrievalResult(x, _distance(query_tokens, self._tokens[x.id]))
            for x in self._listings.values()
            if all(_OPS[op](getattr(x, col), value) for col, op, value in filters)
        ]
        results.sort(key=lambda r: (r.distance, str(r.listing.id)))  # deterministic
        return results[:limit]

    def photos_by_set(self, set_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[Photo]]:
        return {
            set_id: [
                Photo(
                    photo_set_id=set_id,
                    source_url=self._photo_url(row["source_url"]),
                    room_type=row["room_type"],
                    position=row["position"],
                    attribution=row.get("attribution"),
                )
                for row in self._photos[set_id]
            ]
            for set_id in set_ids
            if set_id in self._photos
        }

    def risk_by_listing(self, listing_ids: Sequence[uuid.UUID]) -> dict[str, RiskAssessment]:
        return {str(i): self._risk[str(i)] for i in listing_ids if str(i) in self._risk}

    def neighborhood(
        self, lat: float, lng: float, *, cache_only: bool = False
    ) -> NeighborhoodResult | None:
        return self._neighborhoods.get(_location_key(lat, lng))

    def commute(self, lat: float, lng: float, work_location: str | None) -> CommuteResult | None:
        return estimate_commute_to(lat, lng, work_location)  # offline estimate, no network

    # -----------------------------------------------------------------------------

    @staticmethod
    def _photo_url(source_url: str) -> str:
        """Serve the local copy when it has been fetched; otherwise keep the hotlink."""
        name = local_photo_name(source_url)
        if (PHOTOS_DIR / name).is_file():
            return f"{PHOTOS_URL_PREFIX}/{name}"
        return source_url


@lru_cache(maxsize=1)
def get_demo_repository() -> DemoRepository:
    return DemoRepository()
