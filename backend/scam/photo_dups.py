"""Photo-duplicate scam signal (T3.2) — pure, no API (ADR-0002, SPEC F7 AC1).

Catches reused/stolen photos: if a listing's pHashes are within a small Hamming
distance of photos on *other* listings, that's the photo-reuse signal. Hamming
distance is computed directly on the hex pHash strings (XOR + popcount), so this is
stdlib-only and unit-testable — the imagehash library is only needed at seed time to
*produce* the hashes, not to compare them.

Scaling note (see imaging.py): brute-force pairwise comparison is fine at a few
hundred photos; production scale would index with multi-index hashing or LSH.

Note both the scam and the genuine "victim" it copied from will fire this signal —
fusion (T3.4) + the other signals separate the two.
"""

from __future__ import annotations

from collections.abc import Iterable

from scam.signals import Signal

DUP_THRESHOLD = 5  # Hamming distance <= this counts as the same photo (0 = identical)


def hamming(a_hex: str, b_hex: str) -> int:
    """Bit difference between two hex pHash strings."""
    return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")


def duplicate_photo_signal(
    *,
    listing_id: str,
    phashes: Iterable[str | None],
    corpus: Iterable[tuple[str, str | None]],
    threshold: int = DUP_THRESHOLD,
) -> Signal | None:
    """Fire if this listing's photos appear on other listings.

    `corpus` is (other_listing_id, phash) for photos across the DB (may include this
    listing's own rows — they're skipped by id).
    """
    corpus_list = [(lid, ph) for lid, ph in corpus if ph is not None and lid != listing_id]

    matched_listings: set[str] = set()
    matched_photos = 0
    for ph in phashes:
        if ph is None:
            continue
        for other_id, other_ph in corpus_list:
            if hamming(ph, other_ph) <= threshold:
                matched_listings.add(other_id)
                matched_photos += 1
                break  # this photo is accounted for; move to the next

    if not matched_listings:
        return None

    severity = min(1.0, 0.5 + 0.1 * matched_photos)  # more reused photos → stronger
    plural = "s" if len(matched_listings) != 1 else ""
    evidence = (
        f"{matched_photos} photo(s) also appear on {len(matched_listings)} other listing{plural}"
    )
    return Signal(name="photo_reuse", severity=severity, source="image", evidence=evidence)
