"""Berlin open data for the rent check, Around this flat and Right now (ADR-0016).

`get_berlin_data()` returns the in-memory implementation in offline demo mode (build files)
and the Supabase/PostGIS one in live mode. Both raise/return the same things.
"""

from __future__ import annotations

from functools import lru_cache

from berlin.repository import BerlinData


@lru_cache(maxsize=1)
def get_berlin_data() -> BerlinData:
    from core.config import settings

    if settings.demo_mode:
        from berlin.local import LocalBerlinData

        return LocalBerlinData()  # raises files.BuildMissing if `make berlin-data` hasn't run
    from berlin.postgres import PostgresBerlinData
    from core.db import get_engine

    return PostgresBerlinData(get_engine())
