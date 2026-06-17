"""Unit tests for the photo-duplicate signal (pure, no DB/API)."""

from scam.photo_dups import duplicate_photo_signal, hamming

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
    )
    assert sig is not None
    assert sig.name == "photo_reuse" and sig.source == "image"
    assert "1 other listing" in sig.evidence


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
    assert duplicate_photo_signal(listing_id="x", phashes=[H], corpus=[("y", H_1BIT)]) is not None
    # Beyond threshold → silent.
    assert (
        duplicate_photo_signal(listing_id="x", phashes=[H], corpus=[("y", H_FAR)], threshold=5)
        is None
    )


def test_severity_scales_with_matched_photos():
    one = duplicate_photo_signal(listing_id="x", phashes=[H], corpus=[("y", H)])
    two = duplicate_photo_signal(listing_id="x", phashes=[H, H], corpus=[("y", H), ("z", H)])
    assert two.severity > one.severity


def test_handles_missing_hashes():
    assert duplicate_photo_signal(listing_id="x", phashes=[None], corpus=[("y", None)]) is None
