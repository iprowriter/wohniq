"""In-memory ListingRepository for endpoint wiring tests (no DB, no network)."""

from __future__ import annotations

from search.retrieval import RetrievalResult


class FakeRepository:
    """Serves the given listings; enrichment, photos and risk are empty by default."""

    def __init__(self, listings=(), retrieval: list[RetrievalResult] | None = None):
        self.listings = {x.id: x for x in listings}
        self.retrieval = retrieval or []

    def random_listings(self, n):
        return list(self.listings.values())[:n]

    def get_listing(self, listing_id):
        return self.listings.get(listing_id)

    def get_listings(self, listing_ids):
        return [self.listings[i] for i in listing_ids if i in self.listings]

    def retrieve(self, criteria, query_text, *, limit):
        return self.retrieval[:limit]

    def photos_by_set(self, set_ids):
        return {}

    def risk_by_listing(self, listing_ids):
        return {}

    def neighborhood(self, lat, lng, *, cache_only=False):
        return None

    def commute(self, lat, lng, work_location):
        return None
