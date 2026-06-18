"""Batch scam scoring — persist a risk_assessment row for every listing.

Runs the full detector (rules + photo duplicates + LLM text) over all listings and
writes one risk_assessment each, so /search and /compare can show the risk badge by
reading a single stored source — no per-request recomputation, no drift between the
two endpoints. Re-run after re-seeding or changing the detector.

Usage:
    uv run python -m scam.score            # full (incl. LLM text pass)
    uv run python -m scam.score --no-llm   # rules + photos only (no Gemini)
"""

from __future__ import annotations

import argparse
from dataclasses import asdict

from sqlalchemy import delete, select

from core.db import get_sessionmaker
from core.logging import configure_logging, get_logger
from data.models import Listing, Photo, RiskAssessment
from scam.detector import assess_listing
from scam.signals import kiez_price_stats

configure_logging()
logger = get_logger(__name__)


def score_all(*, skip_text: bool = False) -> int:
    factory = get_sessionmaker()
    with factory() as session:
        listings = list(session.scalars(select(Listing)))
        photos = list(session.scalars(select(Photo)))
        if not listings:
            raise SystemExit("No listings. Run `make seed` first.")

        phashes_by_set: dict[str, list[str]] = {}
        for p in photos:
            phashes_by_set.setdefault(str(p.photo_set_id), []).append(p.phash)

        def listing_phashes(x: Listing) -> list[str]:
            return phashes_by_set.get(str(x.photo_set_id), [])

        corpus = [(str(x.id), h) for x in listings for h in listing_phashes(x)]

        ppm2_by_kiez: dict[str, list[float]] = {}
        for x in listings:
            ppm2_by_kiez.setdefault(x.kiez, []).append(x.kaltmiete_eur / x.size_m2)
        stats = {k: kiez_price_stats(v) for k, v in ppm2_by_kiez.items()}

        # Full rescore: clear and rewrite.
        session.execute(delete(RiskAssessment))
        session.commit()

        for x in listings:
            median, mad = stats[x.kiez]
            result = assess_listing(
                listing_id=str(x.id),
                kiez=x.kiez,
                eur_per_m2=x.kaltmiete_eur / x.size_m2,
                anmeldung_possible=x.anmeldung_possible,
                median_eur_per_m2=median,
                mad_eur_per_m2=mad,
                phashes=listing_phashes(x),
                photo_corpus=corpus,
                contact_text=x.contact_text,
                skip_text=skip_text,
            )
            session.add(
                RiskAssessment(
                    listing_id=x.id,
                    score=result.score,
                    band=result.band,
                    signals=[asdict(s) for s in result.signals],
                    engine_version="v1",
                )
            )
        session.commit()

    logger.info("Scored %d listings into risk_assessment.", len(listings))
    return len(listings)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-score listings into risk_assessment.")
    parser.add_argument("--no-llm", action="store_true", help="Skip the LLM text pass")
    args = parser.parse_args()
    score_all(skip_text=args.no_llm)


if __name__ == "__main__":
    main()
