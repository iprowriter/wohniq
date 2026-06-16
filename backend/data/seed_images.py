"""Seed photos for each listing's photo set (T1.5).

Flow:
  1. Read the distinct photo_set_ids from the listing table. (photo_reuse scams
     already share a victim's id from T1.4, so creating one set per *distinct* id
     makes those listings share identical photos — the duplicate-photo signal.)
  2. Build typed room pools from Pexels (cached to disk so re-runs skip the network
     and stay reproducible), computing a pHash per pool image once.
  3. Deterministically assign one photo per room type to each set.
  4. Write photo rows (URL + room_type + pHash + attribution).

Usage:
    uv run python -m data.seed_images                 # uses cached pool if present
    uv run python -m data.seed_images --refresh-pool  # re-fetch from Pexels
    uv run python -m data.seed_images --reset         # replace existing photos

Run AFTER data.seed_listings.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, distinct, func, select

from core.db import get_sessionmaker
from core.logging import configure_logging, get_logger
from data.imaging import phash_from_bytes
from data.models import Listing, Photo
from data.pexels import fetch_all_pools, fetch_image_bytes
from data.photo_assign import ROOM_TYPES, assign_photos

configure_logging()
logger = get_logger(__name__)

GENERATED_DIR = Path(__file__).parent / "generated"
POOL_CACHE = GENERATED_DIR / "photo_pool.json"


def build_pools(per_page: int, refresh: bool) -> dict[str, list[dict]]:
    """Return room pools with a pHash per photo, using the disk cache when possible."""
    if POOL_CACHE.exists() and not refresh:
        logger.info("Using cached photo pool: %s", POOL_CACHE)
        return json.loads(POOL_CACHE.read_text())

    logger.info("Fetching room pools from Pexels (%d per type)…", per_page)
    pools = fetch_all_pools(per_page)
    for room_type, photos in pools.items():
        for photo in photos:
            try:
                photo["phash"] = phash_from_bytes(fetch_image_bytes(photo["source_url"]))
            except Exception as exc:  # noqa: BLE001 — skip a bad image, don't abort
                logger.warning("phash failed for %s: %s", photo["source_url"], exc)
                photo["phash"] = None
        logger.info("  %s: %d photos", room_type, len(photos))

    GENERATED_DIR.mkdir(exist_ok=True)
    POOL_CACHE.write_text(json.dumps(pools, indent=2))
    return pools


def seed(seed_value: int, per_page: int, reset: bool, refresh_pool: bool) -> None:
    factory = get_sessionmaker()
    with factory() as session:
        set_ids = list(session.scalars(select(distinct(Listing.photo_set_id))))
        if not set_ids:
            sys.exit("No listings found. Run `python -m data.seed_listings` first.")

        existing = session.scalar(select(func.count()).select_from(Photo))
        if existing and not reset:
            sys.exit(f"{existing} photos already exist. Re-run with --reset to replace them.")

        pools = build_pools(per_page, refresh_pool)
        rows = assign_photos(set_ids, pools, seed=seed_value)

        if reset and existing:
            logger.info("Resetting: deleting %d existing photos", existing)
            session.execute(delete(Photo))
            session.commit()

        session.add_all(Photo(**row) for row in rows)
        session.commit()

    logger.info(
        "Seeded %d photos across %d sets (%d per set).",
        len(rows),
        len(set_ids),
        len(ROOM_TYPES),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed listing photos from Pexels.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-page", type=int, default=30, help="Pool size per room type")
    parser.add_argument("--reset", action="store_true", help="Replace existing photos")
    parser.add_argument("--refresh-pool", action="store_true", help="Re-fetch pool from Pexels")
    args = parser.parse_args()
    seed(args.seed, args.per_page, args.reset, args.refresh_pool)


if __name__ == "__main__":
    main()
