"""Enrich a page of search results quickly (ADR-0022).

Trip times (BVG/VBB) and neighbourhood counts (OSM Overpass) are free outside services
that can take seconds per call. Looking them up one listing after another made a live
search wait for every call in turn. Here:

  1. both caches are read for the whole page in two queries;
  2. the misses are looked up in parallel. A lookup holds no database connection while
     it waits on the outside service (the free Supabase pooler has few connections, and
     holding them stalled every query); a live answer is then stored in the cache in a
     short session of its own;
  3. whatever hasn't answered within `timeout_s` gets the offline answer: the trip
     estimate (labelled "estimate" on the page, ADR-0008/0009) and the bundled
     neighbourhood data. Late lookups still finish in the background and fill the cache,
     so the next search has them.

The same location is never looked up twice at once.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from core.logging import get_logger
from data.models import CommuteCache, NeighborhoodCache
from enrich.commute import _origin_key, estimate_commute_to, fetch_live_commute, store_commute
from enrich.commute_parse import CommuteResult
from enrich.neighborhood import (
    _from_cache,
    _location_key,
    fetch_neighborhood,
    store_neighborhood,
)
from enrich.neighborhood_parse import NeighborhoodResult

logger = get_logger(__name__)

# Overpass allows few parallel requests per address; transport.rest is more relaxed.
_overpass = ThreadPoolExecutor(max_workers=2, thread_name_prefix="overpass")
_vbb = ThreadPoolExecutor(max_workers=6, thread_name_prefix="vbb")
_lock = threading.Lock()
# Cache writes go one at a time: the free Supabase pooler allows 15 connections in total
# (shared with every other client), so the lookups add at most one.
_write = threading.Lock()
_in_flight: dict[tuple, Future] = {}

Point = tuple[float, float]
Enriched = tuple[NeighborhoodResult | None, CommuteResult | None]


def _submit(pool: ThreadPoolExecutor, key: tuple, fn: Callable, *args: object) -> Future:
    """Run `fn` for `key` unless the same lookup is already running; share its future."""
    with _lock:
        running = _in_flight.get(key)
        if running is not None:
            return running
        fut = pool.submit(fn, *args)
        _in_flight[key] = fut

    def done(_: Future) -> None:
        with _lock:
            _in_flight.pop(key, None)

    fut.add_done_callback(done)
    return fut


def _store(sessions: Callable[[], Session], store: Callable, *args: object) -> None:
    try:
        with _write, sessions() as session:
            store(session, *args)
    except Exception as exc:  # the answer is still used; only the cache misses out
        logger.warning("enrich cache write failed: %s", type(exc).__name__)


def _neighborhood_lookup(
    sessions: Callable[[], Session], lat: float, lng: float
) -> NeighborhoodResult | None:
    result = fetch_neighborhood(lat, lng)
    if result is not None:
        _store(sessions, store_neighborhood, lat, lng, result)
    return result


def _commute_lookup(
    sessions: Callable[[], Session], lat: float, lng: float, work_location: str
) -> CommuteResult | None:
    result, _ = fetch_live_commute(lat, lng, work_location)
    if result is not None:
        _store(sessions, store_commute, lat, lng, work_location, result)
    return result


def enrich_page(
    session: Session,
    sessions: Callable[[], Session],
    points: list[Point],
    work_location: str | None,
    *,
    timeout_s: float,
    offline_neighborhood: Callable[[float, float], NeighborhoodResult | None],
) -> list[Enriched]:
    """(neighbourhood, commute) for each point, in order, within about `timeout_s`."""
    if not points:
        return []
    n_keys = [_location_key(lat, lng) for lat, lng in points]
    rows = session.scalars(
        select(NeighborhoodCache).where(NeighborhoodCache.location_key.in_(set(n_keys)))
    )
    n_cached = {r.location_key: _from_cache(r) for r in rows}

    dest = work_location.strip().lower() if work_location else ""
    c_keys = [_origin_key(lat, lng) for lat, lng in points]
    c_cached: dict[str, CommuteResult] = {}
    if dest:
        rows = session.scalars(
            select(CommuteCache).where(
                tuple_(CommuteCache.origin_key, CommuteCache.dest_key).in_(
                    [(k, dest) for k in set(c_keys)]
                )
            )
        )
        c_cached = {r.origin_key: CommuteResult(r.minutes, r.changes, r.walk_minutes) for r in rows}

    n_futs: dict[int, Future] = {}
    c_futs: dict[int, Future] = {}
    for i, (lat, lng) in enumerate(points):
        if n_keys[i] not in n_cached:
            n_futs[i] = _submit(
                _overpass, ("n", n_keys[i]), _neighborhood_lookup, sessions, lat, lng
            )
        if dest and c_keys[i] not in c_cached:
            c_futs[i] = _submit(
                _vbb,
                ("c", c_keys[i], dest),
                _commute_lookup,
                sessions,
                lat,
                lng,
                work_location,
            )

    pending = [*n_futs.values(), *c_futs.values()]
    if pending:
        wait(pending, timeout=timeout_s)

    def result(fut: Future | None) -> object:
        if fut is None or not fut.done() or fut.exception() is not None:
            return None
        return fut.result()

    late = 0
    out: list[Enriched] = []
    for i, (lat, lng) in enumerate(points):
        neigh = n_cached.get(n_keys[i]) or result(n_futs.get(i))
        if neigh is None:
            late += i in n_futs
            neigh = offline_neighborhood(lat, lng)
        commute: CommuteResult | None = None
        if dest:
            commute = c_cached.get(c_keys[i]) or result(c_futs.get(i))
            if commute is None:
                late += i in c_futs
                commute = estimate_commute_to(lat, lng, work_location)
        out.append((neigh, commute))  # type: ignore[arg-type]
    logger.info(
        "enrich page=%d neighbourhood_cached=%d commute_cached=%d looked_up=%d offline=%d",
        len(points),
        len(n_cached),
        len(c_cached),
        len(pending),
        late,
    )
    return out
