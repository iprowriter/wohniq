"""The `BerlinData` interface: what the rent check and place profile ask of the Berlin data.

Two implementations answer it the same way (ADR-0016): `LocalBerlinData` (offline demo mode,
reads the build files) and `PostgresBerlinData` (live mode, Supabase/PostGIS). Distances are
great-circle metres on PostGIS's sphere in both (berlin/geo.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

POINT_LAYERS = ("schools", "kitas", "playgrounds", "accidents")


@dataclass(frozen=True)
class Address:
    id: int
    street: str
    house_number: str
    postcode: str
    district: str
    location_class: str  # simple | medium | good
    east: bool  # former East Berlin (decides the 1973–1990 Mietspiegel rows)
    plr_id: str
    lat: float
    lng: float

    @property
    def label(self) -> str:
        return f"{self.street} {self.house_number}, {self.postcode} Berlin"


@dataclass(frozen=True)
class Stop:
    id: str
    name: str
    modes: tuple[str, ...]  # sbahn, ubahn, tram, bus, ferry, regional; () = unknown
    lat: float
    lng: float
    distance_m: float


@dataclass(frozen=True)
class Park:
    name: str
    area_m2: int
    distance_m: float  # 0 when the point is inside the park
    lat: float
    lng: float


@dataclass(frozen=True)
class AirStation:
    code: str
    name: str
    station_type: str
    lqi: int | None
    measured_at: str | None
    distance_m: float
    lat: float
    lng: float


@dataclass(frozen=True)
class Area:
    """A planning area with its district region (crime is published per region)."""

    plr_id: str
    plr_name: str
    bzr_id: str
    bzr_name: str
    district: str


class BerlinData(Protocol):
    # addresses
    def search_addresses(self, query: str, limit: int = 10) -> list[Address]: ...
    def address(self, address_id: int) -> Address | None: ...
    def nearest_address(
        self, lat: float, lng: float, district: str | None = None
    ) -> Address | None: ...
    def location_class_share(self, lat: float, lng: float, radius_m: float) -> dict[str, float]: ...

    # areas
    def area_at(self, lat: float, lng: float) -> Area | None: ...
    def crime(self, bzr_id: str) -> float | None: ...
    def crime_rates(self) -> dict[str, float]: ...
    def berlin_crime_rate(self) -> float: ...
    def area_stats(self) -> dict[str, dict[str, float]]: ...

    # around a point
    def nearest_stops(
        self, lat: float, lng: float, limit: int = 6, modes: frozenset[str] | None = None
    ) -> list[Stop]: ...
    def within(self, layer: str, lat: float, lng: float, radius_m: float) -> list[dict]: ...
    def nearest_park(self, lat: float, lng: float) -> Park | None: ...
    def nearest_air_station(self, lat: float, lng: float) -> AirStation | None: ...

    # rent index
    def rent_rows(self) -> list[dict]: ...
    def rent_periods(self) -> dict[str, dict]: ...
    def checklist(self) -> list[dict]: ...
    def manifest(self) -> dict: ...
