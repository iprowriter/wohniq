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

Reuse only counts when at least MIN_SHARED_PHOTOS of this listing's photos match *one*
other listing (ADR-0017). A copied listing takes the whole set (all 5 photos), while the
demo's honest listings share at most 3 stock photos by chance; counting any single match
flagged every listing.
"""

from __future__ import annotations

from collections.abc import Iterable

from scam.signals import Signal

DUP_THRESHOLD = 5  # Hamming distance <= this counts as the same photo (0 = identical)
MIN_SHARED_PHOTOS = 4  # photos that must match one other listing for the signal to fire


def hamming(a_hex: str, b_hex: str) -> int:
    """Bit difference between two hex pHash strings."""
    return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")


def duplicate_photo_signal(
    *,
    listing_id: str,
    phashes: Iterable[str | None],
    corpus: Iterable[tuple[str, str | None]],
    threshold: int = DUP_THRESHOLD,
    min_shared: int = MIN_SHARED_PHOTOS,
) -> Signal | None:
    """Fire if at least `min_shared` of this listing's photos appear on one other listing.

    `corpus` is (other_listing_id, phash) for photos across the DB (may include this
    listing's own rows — they're skipped by id).
    """
    corpus_list = [(lid, ph) for lid, ph in corpus if ph is not None and lid != listing_id]
    own = [ph for ph in phashes if ph is not None]

    shared_with: dict[str, int] = {}  # other listing → how many of our photos it has
    for ph in own:
        matched_here = {oid for oid, oph in corpus_list if hamming(ph, oph) <= threshold}
        for oid in matched_here:
            shared_with[oid] = shared_with.get(oid, 0) + 1

    copies = {oid: n for oid, n in shared_with.items() if n >= min_shared}
    if not copies:
        return None

    most = max(copies.values())
    severity = min(1.0, 0.5 + 0.1 * most)  # more reused photos → stronger
    others = len(copies)
    evidence = (
        f"{most} of {len(own)} photos also appear on "
        + ("another listing" if others == 1 else f"{others} other listings")
    )
    return Signal(name="photo_reuse", severity=severity, source="image", evidence=evidence)
