"""The Berlin Neighbourhoods data bundle: 143 areas × sourced metrics (read-only).

Built by data/neighborhoods/build_index.py (`make neighborhoods-data`) and validated on
load, so an inconsistent file (unknown metric or source, a distribution that doesn't
cover every area, a pending metric with data) fails at startup rather than ranking on
bad data. The API never writes anything and needs no database.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from lifestyle.profiles import CityFigure, Source
from neighborhoods.catalog import METRICS, METRICS_BY_ID, Metric

BUNDLE_PATH = Path(__file__).resolve().parents[1] / "data" / "neighborhoods" / "neighborhoods.json"
SCHEMA_VERSION = 1


class Value(BaseModel):
    raw: float
    source_id: str
    year: str
    method: str
    count: int | None = None  # absolute number behind a rate (e.g. accidents)
    # % of residents per class, for class-based measures ({"best": 42.5, …} or MSS
    # {"high": 10.0, "middle": 70.0, "low": 20.0, "very_low": 0.0}).
    shares: dict[str, float] | None = None


class Reference(BaseModel):
    berlin: float
    berlin_method: str
    # Every area's value, sorted ascending: the fixed yardstick a value is read against.
    distribution: list[float] = Field(min_length=2)

    @model_validator(mode="after")
    def _sorted(self) -> Reference:
        if self.distribution != sorted(self.distribution):
            raise ValueError("distribution must be sorted")
        return self


class Area(BaseModel):
    key: str = Field(pattern=r"^\d{6}$")
    name: str
    district: str
    area_group: str  # the Prognoseraum, e.g. "Kreuzberg Nord"
    population: int = Field(ge=0)
    centroid: tuple[float, float]  # (lat, lng), where residents live
    area_km2: float
    rent_range: tuple[float, float] | None = None
    values: dict[str, Value]


class NeighbourhoodBundle(BaseModel):
    schema_version: int
    inputs: dict[str, str] = Field(default_factory=dict)
    sources: dict[str, Source]
    # Berlin-wide figures without a per-area breakdown (e.g. income per taxpayer), shown
    # as context next to the category they belong to.
    city: dict[str, CityFigure] = Field(default_factory=dict)
    references: dict[str, Reference]
    regions: list[Area]

    @model_validator(mode="after")
    def _consistent(self) -> NeighbourhoodBundle:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version {self.schema_version} != {SCHEMA_VERSION}")
        n = len(self.regions)
        if len({r.key for r in self.regions}) != n:
            raise ValueError("duplicate area keys")
        for fid, fig in self.city.items():
            if fig.source_id not in self.sources:
                raise ValueError(f"city figure {fid!r} cites unknown source {fig.source_id!r}")
        for mid, ref in self.references.items():
            metric = METRICS_BY_ID.get(mid)
            if metric is None:
                raise ValueError(f"reference for unknown metric {mid!r}")
            if metric.requires:
                raise ValueError(f"{mid!r} is marked pending but has data; drop `requires`")
            if len(ref.distribution) != n:
                raise ValueError(f"{mid!r}: distribution covers {len(ref.distribution)} of {n}")
        for r in self.regions:
            for mid, v in r.values.items():
                if mid not in self.references:
                    raise ValueError(f"{r.key}: {mid!r} has no reference")
                if v.source_id not in self.sources:
                    raise ValueError(f"{r.key}: {mid!r} cites unknown source {v.source_id!r}")
            missing = set(self.references) - set(r.values)
            if missing:
                raise ValueError(f"{r.key}: no value for {sorted(missing)}")
        return self

    # --- Queries -----------------------------------------------------------------------

    def area(self, key: str) -> Area | None:
        return self._by_key().get(key)

    def _by_key(self) -> dict[str, Area]:
        cached = self.__dict__.get("_index")
        if cached is None:
            cached = {r.key: r for r in self.regions}
            self.__dict__["_index"] = cached
        return cached

    def available(self) -> list[Metric]:
        return [m for m in METRICS if m.id in self.references]

    def pending(self) -> list[Metric]:
        return [m for m in METRICS if m.id not in self.references]


def load_bundle(path: Path = BUNDLE_PATH) -> NeighbourhoodBundle:
    return NeighbourhoodBundle.model_validate_json(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_bundle() -> NeighbourhoodBundle:
    """The shipped bundle, parsed and validated once per process."""
    return load_bundle()
