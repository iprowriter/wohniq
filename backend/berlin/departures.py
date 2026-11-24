"""Right now: the nearest stops (always, offline-correct) and live departures when online.

The stop list comes from the Berlin data (no network). Live departures come from the free,
keyless transport.rest API (BVG endpoint first, VBB as a fallback) for the nearest S/U-Bahn
station and the nearest bus/tram stop, merged by time. Short timeouts and a 30 s cache keep
the page fast; any failure falls back to the stop list, labelled offline. Switch the live call
off with WOHNIQ_LIVE_DEPARTURES=0 (e.g. for a fully offline demo).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import httpx

from berlin.measures import RAIL
from berlin.profile import walk_min
from berlin.repository import BerlinData, Stop
from core.logging import get_logger

logger = get_logger(__name__)

API_BASES = ("https://v6.bvg.transport.rest", "https://v6.vbb.transport.rest")
TIMEOUT_S = 3.0
CACHE_S = 30.0
WINDOW_MIN = 30
MAX_DEPARTURES = 8
RAIL_MAX_M = 1500  # look for live departures at a station this close at most
SURFACE_MAX_M = 800
SURFACE = frozenset({"bus", "tram"})

PRODUCT_MODE = {
    "suburban": "sbahn",
    "subway": "ubahn",
    "tram": "tram",
    "bus": "bus",
    "ferry": "ferry",
    "regional": "regional",
    "express": "regional",
}


@dataclass
class StopOut:
    id: str
    name: str
    modes: list[str]
    distance_m: int
    walk_minutes: int
    lat: float
    lng: float


@dataclass
class Departure:
    line: str
    mode: str
    direction: str
    stop: str
    when: str | None  # ISO time incl. delay
    planned: str | None
    delay_minutes: int | None
    platform: str | None
    cancelled: bool


@dataclass
class RightNow:
    status: str  # "live" | "offline"
    note: str
    stops: list[StopOut]
    departures: list[Departure] = field(default_factory=list)
    fetched_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_cache: dict[str, tuple[float, list[Departure]]] = {}
_lock = threading.Lock()
_reachable: tuple[float, bool] | None = None
REACHABLE_CACHE_S = 60.0


def departures_reachable() -> bool:
    """Whether the live departures API answers (cached for a minute; 2 s timeout)."""
    global _reachable
    now = time.monotonic()
    if _reachable and now - _reachable[0] < REACHABLE_CACHE_S:
        return _reachable[1]
    ok = False
    for base in API_BASES:
        try:
            ok = httpx.get(f"{base}/stops/900100003", timeout=2.0).status_code < 500
        except httpx.HTTPError:
            ok = False
        if ok:
            break
    _reachable = (now, ok)
    return ok


def api_stop_id(stop_id: str) -> str:
    """'de:11000:900007104' → '900007104' (transport.rest uses the numeric id)."""
    return stop_id.split(":")[2] if stop_id.count(":") >= 2 else stop_id


def parse_departures(payload: dict | list) -> list[Departure]:
    items = payload.get("departures", []) if isinstance(payload, dict) else payload
    out = []
    for d in items:
        line = d.get("line") or {}
        delay = d.get("delay")
        out.append(
            Departure(
                line=line.get("name") or "",
                mode=PRODUCT_MODE.get(line.get("product") or "", "bus"),
                direction=(d.get("direction") or "").strip(),
                stop=((d.get("stop") or {}).get("name") or "").replace(" (Berlin)", ""),
                when=d.get("when") or d.get("plannedWhen"),
                planned=d.get("plannedWhen"),
                delay_minutes=round(delay / 60) if isinstance(delay, int | float) else None,
                platform=d.get("platform"),
                cancelled=bool(d.get("cancelled")),
            )
        )
    return out


def fetch_departures(stop_id: str, client: httpx.Client | None = None) -> list[Departure]:
    """Live departures for one stop; raises on failure (callers fall back)."""
    key = api_stop_id(stop_id)
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_S:
            return hit[1]
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S)
    try:
        last: Exception | None = None
        for base in API_BASES:
            try:
                resp = client.get(
                    f"{base}/stops/{key}/departures",
                    params={"duration": WINDOW_MIN, "results": 12, "remarks": "false"},
                )
                resp.raise_for_status()
                deps = parse_departures(resp.json())
                with _lock:
                    _cache[key] = (now, deps)
                return deps
            except (httpx.HTTPError, ValueError) as exc:
                last = exc
        raise last or RuntimeError("no departures API")
    finally:
        if own:
            client.close()


def _stop_out(s: Stop) -> StopOut:
    return StopOut(
        s.id, s.name, list(s.modes), round(s.distance_m), walk_min(s.distance_m), s.lat, s.lng
    )


def live_targets(data: BerlinData, lat: float, lng: float) -> list[Stop]:
    """The nearest S/U-Bahn station and the nearest bus/tram stop (if close enough)."""
    targets = []
    rail = data.nearest_stops(lat, lng, limit=1, modes=RAIL)
    if rail and rail[0].distance_m <= RAIL_MAX_M:
        targets.append(rail[0])
    surface = data.nearest_stops(lat, lng, limit=2, modes=SURFACE)
    for s in surface:
        if s.distance_m <= SURFACE_MAX_M and all(s.id != t.id for t in targets):
            targets.append(s)
            break
    return targets


def right_now(
    data: BerlinData, lat: float, lng: float, *, live: bool = True, fetch=fetch_departures
) -> RightNow:
    nearest = data.nearest_stops(lat, lng, limit=6)
    stops = [_stop_out(s) for s in nearest]
    first = stops[0] if stops else None
    offline_note = (
        f"Nearest stop: {first.name} · {first.walk_minutes} min walk. " if first else ""
    ) + "Live departures appear when there's a connection."
    if not live:
        return RightNow("offline", offline_note, stops)

    targets = live_targets(data, lat, lng)
    if not targets:
        return RightNow("offline", offline_note, stops)
    departures: list[Departure] = []
    failures = 0
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        for _target, result in zip(
            targets, pool.map(lambda s: _safe(fetch, s.id), targets), strict=True
        ):
            if result is None:
                failures += 1
            else:
                departures += result
    if failures == len(targets):
        return RightNow("offline", offline_note, stops)
    departures = sorted((d for d in departures if d.when), key=lambda d: d.when or "")[
        :MAX_DEPARTURES
    ]
    names = " and ".join(t.name for t in targets)
    return RightNow(
        "live",
        f"Live departures at {names}.",
        stops,
        departures,
        datetime.now(UTC).isoformat(timespec="seconds"),
    )


def _safe(fetch, stop_id: str) -> list[Departure] | None:
    try:
        return fetch(stop_id)
    except Exception as exc:  # noqa: BLE001 - any failure means "show the offline list"
        logger.info("Live departures unavailable for %s: %s", stop_id, type(exc).__name__)
        return None
