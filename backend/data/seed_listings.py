"""Seed the database with synthetic listings (T1.4).

Generates listings via the pure generator, writes them to the `listing` table, and
saves a label manifest (ground truth + hard-negative flags) for the scam eval.

Usage:
    uv run python -m data.seed_listings                 # default 100 listings, seed 42
    uv run python -m data.seed_listings --count 120 --seed 7
    uv run python -m data.seed_listings --reset         # replace existing listings

Refuses to run if listings already exist unless `--reset` is passed (so you don't
silently double-seed). Reset deletes listings — embeddings and risk rows cascade;
photos (keyed by photo_set_id, re-seeded in T1.5) are cleared too.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

from core.db import get_sessionmaker
from core.logging import configure_logging, get_logger
from data.models import Listing, Photo
from data.synthetic import generate_listings, manifest_entry

configure_logging()
logger = get_logger(__name__)

GENERATED_DIR = Path(__file__).parent / "generated"
MANIFEST_PATH = GENERATED_DIR / "seed_manifest.json"


def _to_orm(s) -> Listing:
    return Listing(
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
        contact_name=s.contact_name,
        contact_email=s.contact_email,
        contact_phone=s.contact_phone,
        contact_text=s.contact_text,
        photo_set_id=s.photo_set_id,
        is_scam=s.is_scam,
        scam_type=s.scam_type,
    )


def seed(count: int, seed_value: int, scam_ratio: float, reset: bool) -> None:
    listings = generate_listings(count, seed=seed_value, scam_ratio=scam_ratio)

    factory = get_sessionmaker()
    with factory() as session:
        existing = session.scalar(select(func.count()).select_from(Listing))
        if existing and not reset:
            sys.exit(
                f"{existing} listings already exist. Re-run with --reset to replace them."
            )
        if reset and existing:
            logger.info("Resetting: deleting %d existing listings (+ photos)", existing)
            session.execute(delete(Photo))
            session.execute(delete(Listing))  # cascades to embeddings + risk
            session.commit()

        session.add_all(_to_orm(s) for s in listings)
        session.commit()

    GENERATED_DIR.mkdir(exist_ok=True)
    manifest = [manifest_entry(s) for s in listings]
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    n_scam = sum(1 for s in listings if s.is_scam)
    n_hard = sum(1 for s in listings if s.is_hard_negative)
    logger.info(
        "Seeded %d listings (%d scams, %d hard negatives). Manifest: %s",
        len(listings),
        n_scam,
        n_hard,
        MANIFEST_PATH,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic WohnIQ listings.")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scam-ratio", type=float, default=0.15)
    parser.add_argument("--reset", action="store_true", help="Replace existing listings")
    args = parser.parse_args()
    seed(args.count, args.seed, args.scam_ratio, args.reset)


if __name__ == "__main__":
    main()
