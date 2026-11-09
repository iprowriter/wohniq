"""Read the Geofabrik OpenStreetMap GeoPackage (stdlib only: sqlite3 + struct).

A GeoPackage is an SQLite file; each feature's geometry is a "GeoPackage binary" blob:
a small header (magic "GP", flags, SRS id, optional envelope) followed by standard WKB.
We only need points and (multi)polygons, so a ~60-line decoder beats a GIS dependency.

Which OSM feature classes count for which attribute is defined once, here
(`AMENITY_CATEGORIES`), so the method shown to users and the code can't drift.
Data © OpenStreetMap contributors, ODbL 1.0 (Geofabrik "free" extract).
"""

from __future__ import annotations

import sqlite3
import struct
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from data.lifestyle.geo import Polygon

# attribute -> (OSM fclasses, walking radius in metres). Points and polygon features
# (e.g. a supermarket mapped as a building outline) both count, once each.
AMENITY_CATEGORIES: dict[str, tuple[frozenset[str], int]] = {
    "cafes": (frozenset({"cafe", "restaurant", "bakery", "food_court", "biergarten"}), 500),
    "everyday": (
        frozenset({"supermarket", "convenience", "pharmacy", "doctors", "chemist", "greengrocer"}),
        500,
    ),
    "nightlife": (frozenset({"bar", "pub", "nightclub", "biergarten"}), 1000),
    "culture": (
        frozenset({"museum", "theatre", "cinema", "arts_centre", "library"}),
        1500,
    ),
    "sport": (
        frozenset({"fitness_centre", "sports_centre", "swimming_pool", "sports_hall", "ice_rink"}),
        1000,
    ),
}

WATER_CLASSES = frozenset({"water", "reservoir", "riverbank"})  # not wetlands
WATER_MIN_M2 = 10_000  # ≥ 1 ha: a lake, river or canal stretch, not a garden pond
FOREST_MIN_M2 = 50_000  # ≥ 5 ha of forest


@dataclass(frozen=True)
class Feature:
    fclass: str
    name: str | None
    point: tuple[float, float] | None  # (lng, lat) for point features
    polygons: list[Polygon] | None  # for polygon features


# --- GeoPackage binary -> WKB -> coordinates ------------------------------------------

_ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def _wkb_offset(blob: bytes) -> int:
    if blob[:2] != b"GP":
        raise ValueError("not a GeoPackage geometry blob")
    flags = blob[3]
    envelope = (flags >> 1) & 0b111
    if envelope not in _ENVELOPE_BYTES:
        raise ValueError(f"bad envelope indicator {envelope}")
    return 8 + _ENVELOPE_BYTES[envelope]


class _Reader:
    def __init__(self, data: bytes, pos: int) -> None:
        self.data, self.pos = data, pos

    def geometry(self) -> tuple[int, object]:
        order = "<" if self.data[self.pos] == 1 else ">"
        (gtype,) = struct.unpack_from(order + "I", self.data, self.pos + 1)
        self.pos += 5
        base = gtype % 1000  # ISO Z/M variants: 1001, 2001, …
        dims = 2 + (gtype // 1000 in (1, 2)) + (gtype // 1000 == 3) * 2
        if base == 1:
            return 1, self._point(order, dims)
        if base == 3:
            return 3, self._polygon(order, dims)
        if base in (4, 6):  # multipoint / multipolygon: a count, then full geometries
            (n,) = struct.unpack_from(order + "I", self.data, self.pos)
            self.pos += 4
            return base, [self.geometry()[1] for _ in range(n)]
        raise ValueError(f"unsupported WKB geometry type {gtype}")

    def _point(self, order: str, dims: int) -> tuple[float, float]:
        values = struct.unpack_from(order + "d" * dims, self.data, self.pos)
        self.pos += 8 * dims
        return values[0], values[1]

    def _polygon(self, order: str, dims: int) -> list[list[tuple[float, float]]]:
        (n_rings,) = struct.unpack_from(order + "I", self.data, self.pos)
        self.pos += 4
        rings = []
        for _ in range(n_rings):
            (n,) = struct.unpack_from(order + "I", self.data, self.pos)
            self.pos += 4
            flat = struct.unpack_from(order + "d" * (n * dims), self.data, self.pos)
            self.pos += 8 * n * dims
            rings.append([(flat[i], flat[i + 1]) for i in range(0, len(flat), dims)])
        return rings


def decode_geometry(blob: bytes) -> tuple[tuple[float, float] | None, list[Polygon] | None]:
    """GeoPackage blob -> (point, None) or (None, polygons)."""
    kind, geom = _Reader(blob, _wkb_offset(blob)).geometry()
    if kind == 1:
        return geom, None  # type: ignore[return-value]
    if kind == 3:
        return None, [geom]  # type: ignore[list-item]
    if kind == 6:
        return None, list(geom)  # type: ignore[arg-type]
    if kind == 4:
        return geom[0], None  # type: ignore[index]  # first point of a multipoint
    raise ValueError(f"unsupported geometry kind {kind}")


def read_layer(gpkg: Path, layer: str, fclasses: frozenset[str] | None = None) -> Iterator[Feature]:
    """Features of one layer, optionally only the given fclasses."""
    con = sqlite3.connect(f"file:{gpkg}?mode=ro", uri=True)
    try:
        query = f'SELECT fclass, name, geom FROM "{layer}"'
        params: tuple = ()
        if fclasses is not None:
            query += f" WHERE fclass IN ({','.join('?' * len(fclasses))})"
            params = tuple(sorted(fclasses))
        for fclass, name, blob in con.execute(query, params):
            if blob is None:
                continue
            point, polygons = decode_geometry(blob)
            yield Feature(fclass, name, point, polygons)
    finally:
        con.close()
