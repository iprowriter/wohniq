"""Berlin open-data endpoints: rent index, address search, Around this flat, Right now.

Read-only and demo-mode safe (the in-memory data in demo mode, Supabase/PostGIS live;
ADR-0016). The rent check for the user's own flat is computed in the browser from
`/rent/index`, so a flat's rent and features are never sent here (ADR-0017). Addresses and
coordinates are public data; nothing is logged beyond counts.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

import berlin as berlin_pkg
from berlin.checklist_en import GROUP_LABELS, INSULATION_ITEMS, LABELS, NOT_APPLICABLE
from berlin.departures import right_now
from berlin.files import BuildMissing
from berlin.profile import build_profile
from berlin.rent import DISCLAIMER_TEXT, EXEMPTIONS_TEXT, rent_by_period
from berlin.repository import BerlinData
from core.config import settings

router = APIRouter(tags=["berlin"])

# Berlin, generously (rejects points the data can't describe).
LAT_RANGE = (52.30, 52.70)
LNG_RANGE = (13.05, 13.80)


def berlin_data() -> BerlinData:
    try:
        return berlin_pkg.get_berlin_data()
    except BuildMissing:
        raise HTTPException(
            status_code=503,
            detail="Berlin data not built on this server. Run `make berlin-data` (ADR-0016).",
        ) from None


Data = Annotated[BerlinData, Depends(berlin_data)]


def _check_point(lat: float, lng: float) -> None:
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
        raise HTTPException(status_code=422, detail="Point is outside Berlin")


def _address_out(a, data: BerlinData | None = None) -> dict:
    out = {
        "id": a.id,
        "label": a.label,
        "street": a.street,
        "house_number": a.house_number,
        "postcode": a.postcode,
        "district": a.district,
        "location_class": a.location_class,
        "east": a.east,
        "lat": a.lat,
        "lng": a.lng,
    }
    if data is not None:
        area = data.area_at(a.lat, a.lng)
        out["planning_area"] = area.plr_name if area else None
        out["district_region"] = area.bzr_name if area else None
        out["location_class_share_300m"] = round(
            data.location_class_share(a.lat, a.lng, 300).get(a.location_class, 0), 2
        )
    return out


@router.get("/rent/index")
def rent_index(response: Response, data: Data) -> dict:
    """Everything the browser needs to run the rent check locally."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    checklist = [
        {
            **item,
            "label": LABELS.get(item["id"], item["text_de"]),
            "not_applicable": sorted(NOT_APPLICABLE.get(item["id"], set())),
        }
        for item in data.checklist()
    ]
    return {
        "source": "Berliner Mietspiegel 2026 (Senatsverwaltung für Stadtentwicklung, Bauen "
        "und Wohnen); reference date 1 September 2025",
        "periods": data.rent_periods(),
        "rows": data.rent_rows(),
        "groups": GROUP_LABELS,
        "checklist": checklist,
        "insulation_items": list(INSULATION_ITEMS),
        "rent_brake_factor": 1.10,
        "group_step": 0.20,
        "new_build_from_year": 2014,
        "no_heating_or_bath_deduction": 0.33,
        "exemptions": EXEMPTIONS_TEXT,
        "disclaimer": DISCLAIMER_TEXT,
        "checklist_note": "The checklist (Orientierungshilfe) is a guide, not part of the "
        "qualified Mietspiegel.",
    }


@router.get("/rent/addresses")
def search_addresses(
    data: Data,
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(10, ge=1, le=25),
) -> list[dict]:
    """Residential addresses whose street and number start with the typed text."""
    return [_address_out(a) for a in data.search_addresses(q, limit)]


@router.get("/rent/addresses/{address_id}")
def get_address(
    address_id: int,
    data: Data,
    size_m2: float | None = Query(None, gt=0, le=500),
) -> dict:
    a = data.address(address_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Address not found")
    out = _address_out(a, data)
    if size_m2:
        out["mean_by_period"] = rent_by_period(
            data.rent_rows(), a.location_class, a.east, size_m2, data.rent_periods()
        )
    return out


@router.get("/place")
def place_profile(
    lat: float,
    lng: float,
    data: Data,
    location_class: str | None = Query(None, pattern="^(simple|medium|good)$"),
) -> dict:
    """Around this point: the eight measures, each placed among Berlin's areas."""
    _check_point(lat, lng)
    return build_profile(data, lat, lng, location_class).to_dict()


@router.get("/right-now")
def get_right_now(lat: float, lng: float, data: Data) -> dict:
    """Nearest stops with walking minutes, plus live departures when reachable."""
    _check_point(lat, lng)
    return right_now(data, lat, lng, live=settings.wohniq_live_departures).to_dict()
