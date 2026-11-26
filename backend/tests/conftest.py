"""Shared test setup.

Keep tests independent of locally downloaded data: `make demo-stops` writes a real VBB
network to data/vbb/, which would otherwise change commute results on machines that have
run it. Tests that need a network pass one in explicitly (see tests/gtfs_fixture.py).
"""

import pytest

import berlin
import enrich.commute as commute


@pytest.fixture(autouse=True)
def no_local_transit_network(monkeypatch):
    monkeypatch.setattr(commute, "get_network", lambda: None)


_local_berlin = None


@pytest.fixture(autouse=True)
def offline_berlin_data(monkeypatch):
    """Berlin data in tests is always the local build (or absent), never Supabase.

    `.env` usually has a real DATABASE_URL; without this, any API test outside demo mode
    would query the live database through the listing enrichment. The parity test builds
    its own Postgres repository explicitly.
    """
    from berlin.files import BuildMissing, is_built

    def local_only():
        global _local_berlin
        if not is_built():
            raise BuildMissing("no Berlin build in this checkout")
        if _local_berlin is None:
            from berlin.local import LocalBerlinData

            _local_berlin = LocalBerlinData()
        return _local_berlin

    monkeypatch.setattr(berlin, "get_berlin_data", local_only)
    import app.main as main

    monkeypatch.setattr(main, "_warm_listing_locations", lambda data: None)


@pytest.fixture(autouse=True)
def _fresh_memos():
    """Process-level memories (ADR-0022) must not leak fake answers between tests."""
    from enrich.commute import _resolve_cached
    from search.explanation import _cache

    _resolve_cached.cache_clear()
    _cache.clear()
    yield
