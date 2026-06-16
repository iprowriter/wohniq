"""Unit tests for the pure photo-assignment logic (no network/DB)."""

import uuid

import pytest

from data.photo_assign import ROOM_TYPES, assign_photos


def _fake_pools(n: int = 8) -> dict[str, list[dict]]:
    return {
        rt: [
            {"source_url": f"https://cdn/{rt}/{i}.jpg", "attribution": f"by P{i}", "phash": f"{i:016x}"}
            for i in range(n)
        ]
        for rt in ROOM_TYPES
    }


def _set_ids(n: int = 5) -> list[uuid.UUID]:
    return [uuid.UUID(int=i) for i in range(n)]


def test_each_set_gets_one_photo_per_room_type():
    sets = _set_ids(5)
    rows = assign_photos(sets, _fake_pools(), seed=1)
    assert len(rows) == 5 * len(ROOM_TYPES)
    for sid in sets:
        set_rows = [r for r in rows if r["photo_set_id"] == sid]
        assert [r["room_type"] for r in set_rows] == ROOM_TYPES
        assert [r["position"] for r in set_rows] == list(range(len(ROOM_TYPES)))


def test_source_url_matches_room_pool():
    rows = assign_photos(_set_ids(4), _fake_pools(), seed=1)
    for r in rows:
        assert f"/{r['room_type']}/" in r["source_url"]


def test_deterministic_for_seed():
    sets = _set_ids(6)
    a = assign_photos(sets, _fake_pools(), seed=7)
    b = assign_photos(sets, _fake_pools(), seed=7)
    assert [r["source_url"] for r in a] == [r["source_url"] for r in b]


def test_empty_pool_raises():
    pools = _fake_pools()
    pools["kitchen"] = []
    with pytest.raises(ValueError, match="kitchen"):
        assign_photos(_set_ids(2), pools, seed=1)
