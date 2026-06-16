"""Pure photo-set assignment — no network, no DB, stdlib only.

Given typed room pools (lists of candidate photos per room type) and the set of
distinct photo_set_ids, deterministically assign one photo per room type to each
set so every listing gets a *coherent* apartment tour (living room + bedroom +
kitchen + bathroom + exterior) rather than five random images.

Kept stdlib-only (like synthetic.py) so the assignment is unit-testable without
hitting Pexels. The network fetch and pHash live in pexels.py / imaging.py.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

# Order is also the on-screen `position` of each photo in the set.
ROOM_TYPES = ["living_room", "bedroom", "kitchen", "bathroom", "exterior"]

# What to ask Pexels for, per room type (used by the Pexels client).
ROOM_QUERIES = {
    "living_room": "modern living room apartment",
    "bedroom": "cozy bedroom apartment",
    "kitchen": "modern kitchen apartment",
    "bathroom": "bathroom interior",
    "exterior": "apartment building facade",
}


def assign_photos(
    set_ids: Sequence,
    pools: dict[str, list[dict]],
    *,
    seed: int = 42,
) -> list[dict]:
    """Return photo rows (one per room type per set) ready to insert.

    Deterministic for a given seed and pool. Each returned dict matches the
    `photo` table columns: photo_set_id, source_url, room_type, position, phash,
    attribution. Sets are processed in sorted id order so output is stable.
    """
    missing = [rt for rt in ROOM_TYPES if not pools.get(rt)]
    if missing:
        raise ValueError(f"empty photo pool(s) for room type(s): {missing}")

    rng = random.Random(seed)
    rows: list[dict] = []
    for set_id in sorted(set_ids, key=str):
        for position, room_type in enumerate(ROOM_TYPES):
            photo = rng.choice(pools[room_type])
            rows.append(
                {
                    "photo_set_id": set_id,
                    "source_url": photo["source_url"],
                    "room_type": room_type,
                    "position": position,
                    "phash": photo.get("phash"),
                    "attribution": photo.get("attribution"),
                }
            )
    return rows
