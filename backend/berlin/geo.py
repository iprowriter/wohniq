"""Distances on a sphere, matching PostGIS `geography` with `use_spheroid => false`.

Both repositories measure the same way (ADR-0016, parity test): the in-memory one with these
NumPy functions, the Postgres one with ST_Distance/ST_DWithin(..., false), which use the
same mean Earth radius.
"""

from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_M = 6371008.7714  # PostGIS sphere radius (mean radius of WGS84)
_M_PER_DEG = math.pi * EARTH_RADIUS_M / 180


def haversine_m(lat: float, lng: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    """Great-circle distance in metres from one point to many."""
    p1, p2 = math.radians(lat), np.radians(lats)
    dphi = p2 - p1
    dlmb = np.radians(lngs) - math.radians(lng)
    a = np.sin(dphi / 2) ** 2 + math.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def haversine_one(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return float(haversine_m(lat1, lng1, np.array([lat2]), np.array([lng2]))[0])


def degree_box(lat: float, radius_m: float) -> tuple[float, float]:
    """Half-sizes (dlat, dlng) in degrees of a box that contains a circle of `radius_m`."""
    dlat = radius_m / _M_PER_DEG
    return dlat, dlat / max(0.01, math.cos(math.radians(lat)))


def local_xy(lat0: float, lng0: float, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    """Metres east/north of (lat0, lng0) in a local equirectangular plane (for outlines)."""
    x = np.radians(lngs - lng0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    y = np.radians(lats - lat0) * EARTH_RADIUS_M
    return np.stack([x, y], axis=-1)


def point_segment_distance(px: float, py: float, seg: np.ndarray) -> np.ndarray:
    """Distance from (px, py) to each segment row (x1, y1, x2, y2), same plane units."""
    x1, y1, x2, y2 = seg[:, 0], seg[:, 1], seg[:, 2], seg[:, 3]
    dx, dy = x2 - x1, y2 - y1
    length2 = dx * dx + dy * dy
    t = np.where(
        length2 > 0, ((px - x1) * dx + (py - y1) * dy) / np.where(length2 > 0, length2, 1), 0
    )
    t = np.clip(t, 0, 1)
    return np.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def points_in_ring(xs: np.ndarray, ys: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Even-odd test of many points against one ring (array of (x, y) vertices)."""
    inside = np.zeros(xs.shape, dtype=bool)
    x1, y1 = ring[:-1, 0], ring[:-1, 1]
    x2, y2 = ring[1:, 0], ring[1:, 1]
    for ax, ay, bx, by in zip(x1, y1, x2, y2, strict=True):
        crosses = (ay > ys) != (by > ys)
        if not crosses.any():
            continue
        xint = ax + (ys - ay) * (bx - ax) / ((by - ay) or 1e-300)
        inside ^= crosses & (xs < xint)
    return inside


def points_in_polygons(
    xs: np.ndarray, ys: np.ndarray, polygons: list[list[np.ndarray]]
) -> np.ndarray:
    """Points inside a multipolygon given as [[outer, hole, …], …] rings (lng, lat)."""
    result = np.zeros(xs.shape, dtype=bool)
    for rings in polygons:
        inside = points_in_ring(xs, ys, rings[0])
        for hole in rings[1:]:
            inside &= ~points_in_ring(xs, ys, hole)
        result |= inside
    return result
