"""Build the text representation of a listing that gets embedded (pure, stdlib).

We embed the *meaning-bearing* fields — what the place is and feels like — and
deliberately exclude price and contact details (price is a hard filter handled by
the ranker, and contact text is the scam detector's job, not the vibe match).
Kept import-light so it's unit-testable without the DB or the Gemini SDK.
"""

from __future__ import annotations


def _rooms_str(rooms: float) -> str:
    return str(int(rooms)) if float(rooms).is_integer() else str(rooms)


def build_embedding_text(listing) -> str:
    """Stitch a listing's descriptive fields into one string for embedding.

    `listing` is any object exposing: title, rooms, size_m2, furnished, kiez,
    district, description (the ORM model or a stand-in).
    """
    furnished = "furnished" if listing.furnished else "unfurnished"
    parts = [
        listing.title,
        f"{_rooms_str(listing.rooms)}-room {furnished} apartment, {listing.size_m2} m²",
        f"in {listing.kiez}, {listing.district}",
        listing.description,
    ]
    return ". ".join(p for p in parts if p)
