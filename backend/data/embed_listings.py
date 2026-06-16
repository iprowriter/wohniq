"""Backfill listing embeddings into pgvector (T1.6).

For every listing without an embedding, build its text representation, get a vector
from Gemini, and store it in `listing_embedding`. Idempotent: only embeds what's
missing, so re-running is cheap. `--reset` re-embeds everything (e.g. after changing
the embedding text or model).

Usage:
    uv run python -m data.embed_listings           # embed listings missing a vector
    uv run python -m data.embed_listings --reset    # re-embed all listings

Run AFTER data.seed_listings.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import delete, select

from core.db import get_sessionmaker
from core.embeddings import EMBED_DIM, embed_texts
from core.logging import configure_logging, get_logger
from data.embed_text import build_embedding_text
from data.models import Listing, ListingEmbedding

configure_logging()
logger = get_logger(__name__)


def backfill(reset: bool) -> None:
    factory = get_sessionmaker()
    with factory() as session:
        listings = list(session.scalars(select(Listing)))
        if not listings:
            sys.exit("No listings found. Run `python -m data.seed_listings` first.")

        if reset:
            logger.info("Resetting: deleting all existing embeddings")
            session.execute(delete(ListingEmbedding))
            session.commit()

        already = set(session.scalars(select(ListingEmbedding.listing_id)))
        todo = [listing_ for listing_ in listings if listing_.id not in already]
        if not todo:
            logger.info("All %d listings already embedded. Nothing to do.", len(listings))
            return

        texts = [build_embedding_text(listing_) for listing_ in todo]
        logger.info("Embedding %d listings (dim=%d)…", len(todo), EMBED_DIM)
        vectors = embed_texts(texts)

        for listing_, vector, text in zip(todo, vectors, texts, strict=True):
            session.add(
                ListingEmbedding(listing_id=listing_.id, embedding=vector, content=text)
            )
        session.commit()

    logger.info("Backfilled %d embeddings.", len(todo))


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill listing embeddings.")
    parser.add_argument("--reset", action="store_true", help="Re-embed all listings")
    args = parser.parse_args()
    backfill(args.reset)


if __name__ == "__main__":
    main()
