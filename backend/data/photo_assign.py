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


def assign_from_existing(
    new_set_ids: Sequence,
    existing_rows: list[dict],
    *,
    seed: int = 4242,
    max_shared: int = 2,
    tries: int = 500,
) -> list[dict]:
    """Photo rows for new sets, drawn from photos already in use (no new downloads).

    Each new set gets one photo per room type and shares at most `max_shared` photos with
    any other set, existing or new, so honest listings never look like a photo copy (the
    scam signal needs 4 shared photos, ADR-0017). Deterministic for a seed.
    """
    pools: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for r in sorted(existing_rows, key=lambda r: (r["room_type"], r["source_url"])):
        if r["source_url"] not in seen:
            seen.add(r["source_url"])
            pools.setdefault(r["room_type"], []).append(r)
    missing = [rt for rt in ROOM_TYPES if not pools.get(rt)]
    if missing:
        raise ValueError(f"no existing photos for room type(s): {missing}")

    sets: dict[str, set[str]] = {}
    for r in existing_rows:
        sets.setdefault(str(r["photo_set_id"]), set()).add(r["source_url"])

    rng = random.Random(seed)
    rows: list[dict] = []
    for set_id in sorted(new_set_ids, key=str):
        for _ in range(tries):
            picks = [rng.choice(pools[rt]) for rt in ROOM_TYPES]
            urls = {p["source_url"] for p in picks}
            if all(len(urls & other) <= max_shared for other in sets.values()):
                break
        else:
            raise ValueError(f"couldn't find photos for set {set_id} sharing <= {max_shared}")
        sets[str(set_id)] = urls
        for position, (room_type, photo) in enumerate(zip(ROOM_TYPES, picks, strict=True)):
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
