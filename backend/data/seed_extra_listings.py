"""Add the 40 extra listings (ADR-0018) to a database that already has the original 100.

    uv run python -m data.seed_extra_listings      # or: make seed-extra

Inserts only listings that aren't there yet (safe to re-run), and gives each new photo set
5 photos drawn from the photos already in the database, sharing at most 2 with any other
set (photo-copy scams reuse a whole existing set instead). No Pexels key needed. Afterwards:
`python -m data.berlin.fair_rents --apply-db`, `make score`, `python -m data.export_demo_data`.
Embeddings for semantic search need Gemini: `make embed` when a key is set.
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from core.db import get_sessionmaker
from data.models import Listing, Photo
from data.photo_assign import assign_from_existing
from data.seed_listings import _to_orm
from data.synthetic import generate_catalogue


def main() -> int:
    extra = generate_catalogue()[100:]
    with get_sessionmaker()() as session:
        have = {str(i) for i in session.scalars(select(Listing.id))}
        if len(have) < 100:
            print("error: seed the original 100 first (make seed && make seed-images).")
            return 1
        new = [x for x in extra if str(x.id) not in have]
        photos = list(session.scalars(select(Photo)))
        known_sets = {str(p.photo_set_id) for p in photos}
        existing_rows = [
            {
                "photo_set_id": p.photo_set_id,
                "source_url": p.source_url,
                "room_type": p.room_type,
                "phash": p.phash,
                "attribution": p.attribution,
            }
            for p in photos
        ]
        need_photos = sorted(
            {x.photo_set_id for x in new if str(x.photo_set_id) not in known_sets}, key=str
        )
        rows = assign_from_existing(need_photos, existing_rows)
        session.add_all(_to_orm(x) for x in new)
        session.add_all(Photo(**r) for r in rows)
        session.commit()
    print(f"Added {len(new)} listings and {len(rows)} photos ({len(need_photos)} new sets).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
