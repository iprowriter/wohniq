"""Berlin-data context for a listing: matched address, location class, nearest station, rent.

Synthetic listings have a random street and a point scattered around their Kiez, so each is
matched to the nearest real residential address *in its own district* (ADR-0016). The listing
then takes that address's location class and East/West for the rent check, and its planning
area for "Around this flat". Only the street is shown; the house number isn't, because the
listing isn't real.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache

from berlin.measures import RAIL
from berlin.profile import walk_min
from berlin.rent import VERDICT_TEXT, RentInput, RentResult, check_rent, explain
from berlin.repository import BerlinData


@dataclass(frozen=True)
class ListingLocation:
    """lat/lng are the matched address's (where the profile is measured), not the
    listing's scattered synthetic point."""

    street: str
    postcode: str
    district: str
    plr_id: str
    planning_area: str | None
    district_region: str | None
    location_class: str
    east: bool
    rail_stop: str | None
    rail_modes: tuple[str, ...]
    rail_walk_minutes: int | None
    lat: float
    lng: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ListingRent:
    result: RentResult
    verdict_text: str
    explanation: str
    estimate: bool = True  # listings never know their checklist features

    def to_dict(self) -> dict:
        return {
            **self.result.to_dict(),
            "verdict_text": self.verdict_text,
            "explanation": self.explanation,
            "estimate": self.estimate,
        }


def listing_location(data: BerlinData, listing) -> ListingLocation | None:
    return _location(data, str(listing.id), listing.lat, listing.lng, listing.district)


@lru_cache(maxsize=4096)
def _location(
    data: BerlinData, listing_id: str, lat: float, lng: float, district: str | None
) -> ListingLocation | None:
    address = data.nearest_address(lat, lng, district=district) or data.nearest_address(lat, lng)
    if address is None:
        return None
    # Everything else is measured at the matched address, so the area name, the nearest
    # station and "Around this flat" can never disagree with the street shown.
    area = data.area_at(address.lat, address.lng)
    rail = data.nearest_stops(address.lat, address.lng, limit=1, modes=RAIL)
    stop = rail[0] if rail else None
    return ListingLocation(
        street=address.street,
        postcode=address.postcode,
        district=address.district,
        plr_id=address.plr_id,
        planning_area=area.plr_name if area else None,
        district_region=area.bzr_name if area else None,
        location_class=address.location_class,
        east=address.east,
        rail_stop=stop.name if stop else None,
        rail_modes=stop.modes if stop else (),
        rail_walk_minutes=walk_min(stop.distance_m) if stop else None,
        lat=address.lat,
        lng=address.lng,
    )


def listing_rent(
    data: BerlinData, listing, location: ListingLocation | None = None
) -> ListingRent | None:
    location = location or listing_location(data, listing)
    year = getattr(listing, "year_built", None)
    if location is None or not year:
        return None
    result = check_rent(
        RentInput(
            location_class=location.location_class,
            east=location.east,
            year_built=year,
            size_m2=listing.size_m2,
            cold_rent_eur=listing.kaltmiete_eur,
        ),
        data.rent_rows(),
        data.rent_periods(),
        data.checklist(),
    )
    return ListingRent(
        result,
        VERDICT_TEXT[result.verdict],
        explain(
            result,
            size_m2=listing.size_m2,
            year_built=year,
            location_class=location.location_class,
            estimate=True,
        ),
    )


def index_bounds(listing) -> tuple[float | None, int | None]:
    """(lowest index value €/m², table row) for a listing, or (None, None) without data.

    Used by the scam price signal (ADR-0017). Missing Berlin data never breaks scoring: it
    falls back to the Kiez-median check.
    """
    from berlin import get_berlin_data
    from berlin.files import BuildMissing

    try:
        data = get_berlin_data()
        rent = listing_rent(data, listing)
    except (BuildMissing, Exception):  # noqa: BLE001 - no data = old price check
        return None, None
    if rent is None or not rent.result.covered or rent.result.row is None:
        return None, None
    return rent.result.low, rent.result.row["row"]


def warm_listing_locations(data: BerlinData, listings) -> int:
    """Match every listing once (startup), so search never waits on the first lookup."""
    if not getattr(data, "remote", False):
        return sum(1 for x in listings if listing_location(data, x) is not None)
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        return sum(1 for loc in pool.map(lambda x: listing_location(data, x), listings) if loc)
