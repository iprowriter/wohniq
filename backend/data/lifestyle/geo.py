"""Small, dependency-free geometry helpers for the Lifestyle Match data build.

Everything works in a local equirectangular projection around Berlin (metres), which
is accurate to well under 1% across the city — plenty for areas, centroids and
walking-distance radii, and it keeps the build free of GIS dependencies.

Polygons are lists of rings of (lng, lat) pairs; the first ring is the outer boundary,
the rest are holes (GeoJSON / WKB convention).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator, Sequence

EARTH_RADIUS_M = 6_371_008.8
LAT0 = 52.52
M_PER_DEG_LAT = math.pi / 180 * EARTH_RADIUS_M
M_PER_DEG_LNG = M_PER_DEG_LAT * math.cos(math.radians(LAT0))

Ring = Sequence[Sequence[float]]  # [(lng, lat), ...]
Polygon = Sequence[Ring]  # [outer, hole, ...]


def to_xy(lng: float, lat: float) -> tuple[float, float]:
    """(lng, lat) -> metres in the local projection."""
    return lng * M_PER_DEG_LNG, lat * M_PER_DEG_LAT


def to_lnglat(x: float, y: float) -> tuple[float, float]:
    return x / M_PER_DEG_LNG, y / M_PER_DEG_LAT


def ring_area_centroid(ring: Ring) -> tuple[float, float, float]:
    """Unsigned area (m²) and centroid (x, y in metres) of a closed (lng, lat) ring."""
    pts = [to_xy(p[0], p[1]) for p in ring]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        cross = x1 * y2 - x2 * y1
        a += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    a /= 2
    if a == 0:
        return 0.0, pts[0][0], pts[0][1]
    return abs(a), cx / (6 * a), cy / (6 * a)


def polygons_area_centroid(polygons: Iterable[Polygon]) -> tuple[float, tuple[float, float]]:
    """Area (m²) and area centroid (lat, lng) of a set of polygons with holes."""
    total = sx = sy = 0.0
    for rings in polygons:
        for i, ring in enumerate(rings):
            a, x, y = ring_area_centroid(ring)
            sign = 1.0 if i == 0 else -1.0  # first ring is the outer boundary
            total += sign * a
            sx += sign * a * x
            sy += sign * a * y
    if total <= 0:
        raise ValueError("Degenerate geometry (non-positive area)")
    lng, lat = to_lnglat(sx / total, sy / total)
    return total, (lat, lng)


def geojson_polygons(geometry: dict) -> list[Polygon]:
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return list(geometry["coordinates"])
    raise ValueError(f"Unsupported geometry type {geometry['type']}")


def _in_ring(x: float, y: float, ring: Ring) -> bool:
    """Ray casting in (lng, lat) space."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygons(lng: float, lat: float, polygons: Iterable[Polygon]) -> bool:
    for rings in polygons:
        if _in_ring(lng, lat, rings[0]) and not any(_in_ring(lng, lat, h) for h in rings[1:]):
            return True
    return False


def bbox(polygons: Iterable[Polygon]) -> tuple[float, float, float, float]:
    """(min_lng, min_lat, max_lng, max_lat) of the outer rings."""
    xs: list[float] = []
    ys: list[float] = []
    for rings in polygons:
        xs.extend(p[0] for p in rings[0])
        ys.extend(p[1] for p in rings[0])
    return min(xs), min(ys), max(xs), max(ys)


def densify_ring(ring: Ring, step_m: float) -> Iterator[tuple[float, float]]:
    """Points (x, y metres) along a ring, at most `step_m` apart (for distance-to-edge)."""
    pts = [to_xy(p[0], p[1]) for p in ring]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:], strict=False):
        length = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, math.ceil(length / step_m))
        for k in range(steps):
            t = k / steps
            yield x1 + t * (x2 - x1), y1 + t * (y2 - y1)


class GridIndex:
    """Uniform-grid spatial index over (x, y) metre points, with an optional tag."""

    def __init__(self, cell_m: float) -> None:
        self.cell = cell_m
        self.cells: dict[tuple[int, int], list[tuple[float, float, str]]] = {}

    def add(self, x: float, y: float, tag: str = "") -> None:
        key = (int(x // self.cell), int(y // self.cell))
        self.cells.setdefault(key, []).append((x, y, tag))

    def _near(self, x: float, y: float, radius: float) -> Iterator[tuple[float, float, str]]:
        r = math.ceil(radius / self.cell)
        cx, cy = int(x // self.cell), int(y // self.cell)
        for i in range(cx - r, cx + r + 1):
            for j in range(cy - r, cy + r + 1):
                yield from self.cells.get((i, j), ())

    def count_within(self, x: float, y: float, radius: float) -> dict[str, int]:
        """Number of points per tag within `radius` metres."""
        counts: dict[str, int] = {}
        r2 = radius * radius
        for px, py, tag in self._near(x, y, radius):
            if (px - x) ** 2 + (py - y) ** 2 <= r2:
                counts[tag] = counts.get(tag, 0) + 1
        return counts

    def nearest(self, x: float, y: float, max_m: float) -> float:
        """Distance (m) to the nearest point, capped at `max_m`."""
        best = max_m * max_m
        for px, py, _ in self._near(x, y, max_m):
            d2 = (px - x) ** 2 + (py - y) ** 2
            if d2 < best:
                best = d2
        return math.sqrt(best)


# --- Dissolve + simplify (region outlines for the map and listing lookup) -------------


def _vertex(p: Sequence[float]) -> tuple[float, float]:
    return round(p[0], 7), round(p[1], 7)


def dissolve(polygons: Iterable[Polygon]) -> list[list[tuple[float, float]]]:
    """Outline rings of the union of edge-matched polygons (shared borders cancel out).

    Works when neighbouring polygons share identical border vertices, as the LOR
    planning areas do; raises ValueError otherwise (a vertex with two outgoing edges).
    """
    edges: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for rings in polygons:
        for ring in rings:
            for a, b in zip(ring, ring[1:], strict=False):
                ka, kb = _vertex(a), _vertex(b)
                if ka == kb:
                    continue
                if (kb, ka) in edges:
                    edges.discard((kb, ka))  # shared border: interior, drop both sides
                else:
                    edges.add((ka, kb))
    successor: dict[tuple[float, float], tuple[float, float]] = {}
    for a, b in sorted(edges):
        if a in successor:
            raise ValueError(f"Outline branches at {a}: polygons don't share vertices")
        successor[a] = b
    rings: list[list[tuple[float, float]]] = []
    while successor:
        start = min(successor)
        ring = [start]
        node = successor.pop(start)
        while node != start:
            ring.append(node)
            node = successor.pop(node)
        ring.append(start)
        rings.append(ring)
    return rings


def simplify_ring(ring: Sequence[Sequence[float]], tolerance_m: float) -> list[tuple[float, float]]:
    """Douglas–Peucker in metres; keeps the ring closed and at least a triangle."""
    pts = [to_xy(p[0], p[1]) for p in ring]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    # Split at the farthest point from the start so closed rings simplify well.
    far = max(
        range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2
    )
    keep[far] = True
    stack = [(0, far), (far, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        (x1, y1), (x2, y2) = pts[i], pts[j]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy) or 1e-9
        best, best_d = -1, -1.0
        for k in range(i + 1, j):
            d = abs(dy * (pts[k][0] - x1) - dx * (pts[k][1] - y1)) / norm
            if d > best_d:
                best, best_d = k, d
        if best_d > tolerance_m:
            keep[best] = True
            stack.extend([(i, best), (best, j)])
    out = [to_lnglat(*p) for p, k in zip(pts, keep, strict=True) if k]
    if len(out) < 4:  # degenerate after simplification: keep the original ring
        out = [to_lnglat(*p) for p in pts]
    return [(round(x, 5), round(y, 5)) for x, y in out]


def rings_to_polygons(rings: list[list[tuple[float, float]]]) -> list[Polygon]:
    """Group rings into polygons: even nesting depth = outer boundary, odd = hole."""

    def contains(outer, ring) -> bool:
        x, y = ring[0]
        return _in_ring(x, y, outer)

    depth = [sum(contains(o, r) for o in rings if o is not r) for r in rings]
    outers = [i for i, d in enumerate(depth) if d % 2 == 0]
    polygons: dict[int, list] = {i: [rings[i]] for i in outers}
    for i, d in enumerate(depth):
        if d % 2 == 1:
            parents = [o for o in outers if contains(rings[o], rings[i])]
            parent = min(parents, key=lambda o: ring_area_centroid(rings[o])[0])
            polygons[parent].append(rings[i])
    return [polygons[i] for i in outers]
