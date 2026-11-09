"""Region outlines (simplified LOR Bezirksregionen) — for the results map and for
finding which region a listing lies in.

Built by data/lifestyle/build_profiles.py into data/lifestyle/regions_geo.json (~250 KB,
GeoJSON, 5 m simplification). Matching listings to regions by their coordinates — not
by their `kiez` label — matters: 23 of the 100 synthetic listings lie outside the
Ortsteil their label names (ADR-0010).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from data.lifestyle import geo

SHAPES_PATH = Path(__file__).resolve().parents[1] / "data" / "lifestyle" / "regions_geo.json"


@dataclass(frozen=True)
class RegionShape:
    key: str
    polygons: list
    bbox: tuple[float, float, float, float]  # min_lng, min_lat, max_lng, max_lat

    def contains(self, lat: float, lng: float) -> bool:
        min_lng, min_lat, max_lng, max_lat = self.bbox
        if not (min_lng <= lng <= max_lng and min_lat <= lat <= max_lat):
            return False
        return geo.point_in_polygons(lng, lat, self.polygons)


class RegionShapes:
    def __init__(self, geojson: dict) -> None:
        self.geojson = geojson
        self.shapes: dict[str, RegionShape] = {}
        for feature in geojson["features"]:
            polygons = geo.geojson_polygons(feature["geometry"])
            key = feature["properties"]["key"]
            self.shapes[key] = RegionShape(key, polygons, geo.bbox(polygons))

    def __contains__(self, key: str) -> bool:
        return key in self.shapes

    def region_of(self, lat: float, lng: float) -> str | None:
        """Key of the region containing the point, or None (outside Berlin)."""
        for key, shape in self.shapes.items():
            if shape.contains(lat, lng):
                return key
        return None


def load_shapes(path: Path = SHAPES_PATH) -> RegionShapes:
    return RegionShapes(json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def get_shapes() -> RegionShapes:
    return load_shapes()
