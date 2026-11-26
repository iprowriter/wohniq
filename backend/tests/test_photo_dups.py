"""Unit tests for the photo-duplicate signal (pure, no DB/API).

Matching is tested with `min_shared=1`; the "4 photos with one other listing" rule
(ADR-0017) has its own tests below.
"""

from scam.photo_dups import MIN_SHARED_PHOTOS, duplicate_photo_signal, hamming

H = "ffffffffffffffff"  # 64 ones
H_1BIT = "fffffffffffffffe"  # differs by 1 bit
H_FAR = "0000000000000000"  # differs by 64 bits


def test_hamming():
    assert hamming(H, H) == 0
    assert hamming(H, H_1BIT) == 1
    assert hamming(H, H_FAR) == 64


def test_fires_on_exact_reuse():
    sig = duplicate_photo_signal(
        listing_id="scam",
        phashes=[H, "abc123"],
        corpus=[("victim", H), ("other", H_FAR)],
        min_shared=1,
    )
    assert sig is not None
    assert sig.name == "photo_reuse" and sig.source == "image"
    assert sig.evidence == "1 of 2 photos also appear on another listing"


def test_ignores_own_listing():
    # Same hash but same listing_id → not a duplicate across listings.
    assert (
        duplicate_photo_signal(listing_id="me", phashes=[H], corpus=[("me", H)])
        is None
    )


def test_silent_when_unique():
    assert (
        duplicate_photo_signal(listing_id="x", phashes=[H], corpus=[("y", H_FAR)])
        is None
    )


def test_near_duplicate_within_threshold():
    assert (
        duplicate_photo_signal(listing_id="x", phashes=[H], corpus=[("y", H_1BIT)], min_shared=1)
        is not None
    )
    # Beyond threshold → silent.
    assert (
        duplicate_photo_signal(listing_id="x", phashes=[H], corpus=[("y", H_FAR)], threshold=5)
        is None
    )


def test_severity_scales_with_matched_photos():
    one = duplicate_photo_signal(listing_id="x", phashes=[H], corpus=[("y", H)], min_shared=1)
    two = duplicate_photo_signal(
        listing_id="x", phashes=[H, H_1BIT], corpus=[("y", H), ("y", H_1BIT)], min_shared=1
    )
    assert two.severity > one.severity


# Five distinct photo hashes, far apart from each other.
SET = ["0000000000000000", "00000000ffffffff", "ffffffff00000000", "ffff0000ffff0000", H]


def test_needs_four_photos_shared_with_one_listing():
    assert MIN_SHARED_PHOTOS == 4
    three = [("victim", h) for h in SET[:3]]
    assert duplicate_photo_signal(listing_id="x", phashes=SET, corpus=three) is None
    four = [("victim", h) for h in SET[:4]]
    sig = duplicate_photo_signal(listing_id="x", phashes=SET, corpus=four)
    assert sig is not None and sig.evidence == "4 of 5 photos also appear on another listing"


def test_photos_spread_over_several_listings_dont_add_up():
    # Two photos on one listing and two on another is chance stock-photo overlap, not a copy.
    corpus = [("a", SET[0]), ("a", SET[1]), ("b", SET[2]), ("b", SET[3])]
    assert duplicate_photo_signal(listing_id="x", phashes=SET, corpus=corpus) is None


def test_full_copy_is_full_strength():
    corpus = [("victim", h) for h in SET]
    sig = duplicate_photo_signal(listing_id="copy", phashes=SET, corpus=corpus)
    assert sig.severity == 1.0 and sig.evidence.startswith("5 of 5 photos")


def test_handles_missing_hashes():
    assert duplicate_photo_signal(listing_id="x", phashes=[None], corpus=[("y", None)]) is None
