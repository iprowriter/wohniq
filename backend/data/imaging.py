"""Perceptual-hash helpers for the scam detector's photo-reuse signal (F7).

`phash_from_bytes` produces a 64-bit perceptual hash (hex string) that stays
similar for visually similar images. `hamming` counts differing bits between two
hashes — 0 = identical, small = near-duplicate, large = different.

Scaling note: at WohnIQ's scale we compare hashes pairwise (brute force), which is
fine for a few hundred images — a 64-bit Hamming compare is ~1 CPU instruction. A
production system at millions of images would index the hashes with multi-index
hashing (MIH) or LSH, or move to learned image embeddings + an ANN index (e.g.
FAISS). The signal is the same; only the lookup changes.
"""

from __future__ import annotations

from io import BytesIO

import imagehash
from PIL import Image


def phash_from_bytes(data: bytes) -> str:
    """Compute the perceptual hash of an image given its raw bytes."""
    with Image.open(BytesIO(data)) as img:
        return str(imagehash.phash(img.convert("RGB")))


def hamming(hash_a: str, hash_b: str) -> int:
    """Hamming distance between two hex pHash strings (number of differing bits)."""
    return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)
