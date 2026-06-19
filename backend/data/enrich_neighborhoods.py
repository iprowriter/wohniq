"""One-off script: populate neighborhood_cache for all listings that don't have one yet."""

import sys

from core.db import get_sessionmaker
from data.models import Listing, NeighborhoodCache
from enrich.neighborhood import get_neighborhood

session_factory = get_sessionmaker()

with session_factory() as session:
    listings = session.query(Listing).all()
    total = len(listings)
    print(f"Found {total} listings")

    hit = skip = fail = 0
    for i, listing in enumerate(listings, 1):
        key = f"{round(listing.lat, 4)},{round(listing.lng, 4)}"
        if session.get(NeighborhoodCache, key) is not None:
            skip += 1
            print(f"[{i}/{total}] SKIP  {listing.id} ({key})")
            continue

        result = get_neighborhood(session, listing.lat, listing.lng)
        if result is None:
            fail += 1
            print(f"[{i}/{total}] FAIL  {listing.id} ({key})")
        else:
            hit += 1
            print(f"[{i}/{total}] OK    {listing.id} ({key}) — {result.counts}")

print(f"\nDone. fetched={hit} skipped={skip} failed={fail}")
sys.exit(1 if fail else 0)
