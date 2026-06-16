"""Pexels API client — fetch typed room-photo pools and raw image bytes.

Free tier (200 req/hour) is far more than we need: one search per room type plus a
one-time byte fetch per pool image to compute its pHash. We store only the CDN URL
(ADR-0003), never the file. Requires PEXELS_API_KEY in .env.
"""

from __future__ import annotations

import httpx

from core.config import settings
from data.photo_assign import ROOM_QUERIES

_SEARCH_URL = "https://api.pexels.com/v1/search"


def _headers() -> dict[str, str]:
    if not settings.pexels_api_key:
        raise RuntimeError("PEXELS_API_KEY is not set. Add it to .env.")
    return {"Authorization": settings.pexels_api_key}


def fetch_pool(room_type: str, per_page: int = 30) -> list[dict]:
    """Fetch a pool of candidate photos for one room type."""
    query = ROOM_QUERIES[room_type]
    params = {"query": query, "per_page": per_page, "orientation": "landscape"}
    resp = httpx.get(_SEARCH_URL, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    photos = resp.json().get("photos", [])
    return [
        {
            "id": p["id"],
            "source_url": p["src"]["large"],
            "attribution": f"Photo by {p['photographer']} on Pexels ({p['photographer_url']})",
        }
        for p in photos
    ]


def fetch_all_pools(per_page: int = 30) -> dict[str, list[dict]]:
    """Fetch a pool for every room type (one API call each)."""
    return {rt: fetch_pool(rt, per_page) for rt in ROOM_QUERIES}


def fetch_image_bytes(url: str) -> bytes:
    """Download an image's bytes once (to compute its pHash, then discard)."""
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return resp.content
