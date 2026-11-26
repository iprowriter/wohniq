"""/search — the end-to-end pipeline (T2.8 + T4.3): parse → retrieve → rank → explain,
now enriched with commute (F5) and neighborhood (F6).

Areas: requested Berlin areas are a hard filter (retrieval). If nothing matches inside
them, we fall back to the closest matching listings within NEARBY_MAX_KM and say so
(`notices`), and every result carries an `area_match` label ("In Mitte" / "Near Mitte ·
2.1 km"). When the budget is what empties the results, a `budget_too_low` notice
recommends the minimum budget that would show flats (search/diagnostics.py).

Enrichment strategy (enrich top-k): rank the candidate pool on the cheap factors first
(relevance, budget, quiet-from-Kiez), take the page, then enrich *only* those listings
with commute + neighborhood and re-rank — so we don't pay ~20 Overpass/transit lookups
per search for listings we'll never show. (Neighborhood lookups can be pre-warmed into
the cache; commute is per-query but cached per origin+destination.)

`is_scam`/`scam_type` are NEVER serialized (AGENTS rule).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.repository import ListingRepository, get_repository
from core.logging import get_logger
from data.kieze import ALL_KIEZE, BERLIN_BBOX
from data.models import Listing, Photo, RiskAssessment
from enrich.commute_parse import CommuteResult
from enrich.neighborhood_parse import DEFAULT_RADIUS_M
from search.areas import NEARBY_MAX_KM, matching_area, nearest_area
from search.criteria import SearchCriteria
from search.diagnostics import (
    BUDGET_TOO_LOW,
    NO_LISTINGS_IN_AREA,
    Notice,
    budget_advice,
    budget_notice,
    nearby_notice,
    no_listings_notice,
    no_results_notice,
    partial_budget_notice,
    requirements_phrase,
)
from search.explain_rules import MatchContext
from search.explanation import Explanation, explain
from search.parser import parse_query
from search.ranking import (
    IN_AREA,
    NEARBY,
    OUTSIDE,
    RankCriteria,
    RankingInput,
    rank,
    score_listing,
)
from search.retrieval import RetrievalResult
from search.similar import Flat as SimilarFlat
from search.similar import rank_similar

logger = get_logger(__name__)
router = APIRouter(tags=["search"])

_NIGHTLIFE = {k.name: k.nightlife for k in ALL_KIEZE}

# Listings examined when looking for nearby flats or diagnosing the budget. The whole
# catalogue is ~100 listings; this keeps the extra passes bounded if it grows.
DIAGNOSIS_LIMIT = 500


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=6, ge=1, le=20)
    # Replaces the budget parsed from `query` — used by the "raise your budget to €X"
    # hint so the user's own words don't have to be rewritten.
    max_warm_rent: int | None = Field(default=None, ge=100, le=20000)


class PhotoOut(BaseModel):
    url: str
    room_type: str
    attribution: str | None = None


class FactorOut(BaseModel):
    name: str
    score: float
    weight: float
    detail: str
    highlight: str = ""


class AreaMatchOut(BaseModel):
    """Where a result is relative to the areas the user asked for."""

    status: str  # in_area | nearby | outside
    area: str  # the requested area it's in, or the nearest one
    distance_km: float | None = None  # from that area's centre (nearby/outside only)
    label: str  # "In Mitte", "Near Mitte · 2.1 km"


class NoticeOut(BaseModel):
    """Why results are missing or come from elsewhere, with a concrete way forward."""

    kind: str  # budget_too_low | budget_too_low_in_some_areas | nearby_results | ...
    title: str
    message: str
    suggested_budget: int | None = None
    comfortable_budget: int | None = None
    options_at_suggested: int | None = None
    options_at_comfortable: int | None = None


class CommuteOut(BaseModel):
    minutes: int
    changes: int | None = None  # None when unknown (straight-line estimates)
    walk_minutes: int | None = None
    estimated: bool = False  # offline estimate, not a live BVG/VBB journey
    source: str = "live"  # "live" | "network" (ADR-0009) | "distance" (ADR-0008)


class NeighborhoodOut(BaseModel):
    summary: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)


class RiskSignalOut(BaseModel):
    name: str
    source: str
    evidence: str
    severity: float


class RiskOut(BaseModel):
    band: str  # low | caution | high
    score: int
    signals: list[RiskSignalOut] = Field(default_factory=list)


class ListingLocationOut(BaseModel):
    """The listing matched to the nearest real address in its district (ADR-0016).

    Only the street is shown: the listing is synthetic, so no house number."""

    street: str
    postcode: str
    district: str
    planning_area: str | None = None
    district_region: str | None = None
    location_class: str  # simple | medium | good (Mietspiegel)
    east: bool
    rail_stop: str | None = None  # nearest S/U-Bahn station
    rail_modes: list[str] = Field(default_factory=list)
    rail_walk_minutes: int | None = None
    # The matched address's point: where maps place the flat (one point per listing).
    lat: float | None = None
    lng: float | None = None
    # Its id, so "Check this rent" can open the rent check at that address.
    address_id: int | None = None


class RentOut(BaseModel):
    """Rent check against the Mietspiegel 2026 (ADR-0017). An estimate: listings don't
    know their checklist features, so the comparable rent is the index mean."""

    verdict: str  # within_limit | above_limit | below_index | new_build | not_covered
    verdict_text: str
    explanation: str
    estimate: bool = True
    covered: bool
    asked: float | None = None  # €/m² net cold
    low: float | None = None
    mean: float | None = None
    high: float | None = None
    limit: float | None = None
    over_per_m2: float | None = None
    over_per_month: float | None = None
    row: int | None = None
    period: str | None = None


class ListingOut(BaseModel):
    id: str
    title: str
    address: str
    kiez: str
    district: str | None
    rooms: float
    size_m2: int
    kaltmiete_eur: int
    nebenkosten_eur: int
    warmmiete_eur: int
    deposit_eur: int | None
    furnished: bool
    available_from: date | None
    photos: list[PhotoOut] = Field(default_factory=list)
    year_built: int | None = None
    location: ListingLocationOut | None = None
    rent: RentOut | None = None


class SearchResultItem(BaseModel):
    listing: ListingOut
    score: float
    factors: list[FactorOut]
    explanation: Explanation
    commute: CommuteOut | None = None
    neighborhood: NeighborhoodOut | None = None
    risk: RiskOut | None = None
    area_match: AreaMatchOut | None = None


class SearchResponse(BaseModel):
    criteria: SearchCriteria
    results: list[SearchResultItem]
    # Shown under the criteria when commute times are estimated or unavailable.
    commute_note: str | None = None
    # Empty / fallback explanations: budget too low, nothing in the area (nearby shown).
    notices: list[NoticeOut] = Field(default_factory=list)


def _to_risk_out(row: RiskAssessment | None) -> RiskOut | None:
    if row is None:
        return None
    signals = [
        RiskSignalOut(
            name=s.get("name", ""),
            source=s.get("source", ""),
            evidence=s.get("evidence", ""),
            severity=float(s.get("severity", 0.0)),
        )
        for s in (row.signals or [])
    ]
    return RiskOut(band=row.band, score=row.score, signals=signals)


def _to_commute_out(commute: CommuteResult | None) -> CommuteOut | None:
    if commute is None:
        return None
    return CommuteOut(
        minutes=commute.minutes,
        changes=commute.changes,
        walk_minutes=commute.walk_minutes,
        estimated=commute.estimated,
        source=commute.source,
    )


def _commute_note(work_location: str | None, commutes: list[CommuteResult | None]) -> str | None:
    if not work_location or not commutes:
        return None
    if all(c is None for c in commutes):
        return f"Couldn't find \"{work_location}\", so commute times aren't shown."
    sources = {c.source for c in commutes if c is not None}
    if "network" in sources:
        return (
            f"Commute times to {work_location} are estimated from the VBB timetable "
            "(weekday peak, 7–9 am); live transit data is unavailable."
        )
    if "distance" in sources:
        return (
            f"Commute times to {work_location} are estimates from straight-line distance "
            "and average transit speeds (live transit data unavailable)."
        )
    return None


def _to_listing_out(listing: Listing, photos: list[Photo]) -> ListingOut:
    # NOTE: is_scam / scam_type are intentionally omitted — they never leave the server.
    return ListingOut(
        id=str(listing.id),
        title=listing.title,
        address=listing.address,
        kiez=listing.kiez,
        district=listing.district,
        rooms=float(listing.rooms),
        size_m2=listing.size_m2,
        kaltmiete_eur=listing.kaltmiete_eur,
        nebenkosten_eur=listing.nebenkosten_eur,
        warmmiete_eur=listing.warmmiete_eur,
        deposit_eur=listing.deposit_eur,
        furnished=listing.furnished,
        available_from=listing.available_from,
        photos=[
            PhotoOut(url=p.source_url, room_type=p.room_type, attribution=p.attribution)
            for p in photos
        ],
        year_built=listing.year_built,
        **_berlin_fields(listing),
    )


def _berlin_fields(listing: Listing) -> dict:
    """location + rent for a listing; empty when the Berlin data isn't available."""
    from berlin import get_berlin_data
    from berlin.files import BuildMissing
    from berlin.listings import listing_location, listing_rent

    try:
        data = get_berlin_data()
        location = listing_location(data, listing)
        rent = listing_rent(data, listing, location)
    except BuildMissing:
        return {}
    except Exception:  # noqa: BLE001 - enrichment must never break search
        logger.warning("Berlin context unavailable for a listing", exc_info=True)
        return {}
    out: dict = {}
    if location is not None:
        out["location"] = ListingLocationOut(
            **{k: v for k, v in location.to_dict().items() if k in ListingLocationOut.model_fields}
        )
    if rent is not None:
        r = rent.result
        out["rent"] = RentOut(
            verdict=r.verdict,
            verdict_text=rent.verdict_text,
            explanation=rent.explanation,
            covered=r.covered,
            asked=r.asked,
            low=r.low,
            mean=r.mean,
            high=r.high,
            limit=r.limit,
            over_per_m2=r.over_per_m2,
            over_per_month=r.over_per_month,
            row=r.row["row"] if r.row else None,
            period=r.period,
        )
    return out


# --- Area fit, ranking inputs, explanation context -------------------------------------

AreaFit = tuple[str, str, float | None]  # (status, area, km from its centre)


def _area_fit(listing: Listing, areas: list[str]) -> AreaFit | None:
    """In one of `areas`, near one (≤ NEARBY_MAX_KM from its centre), or outside."""
    if not areas:
        return None
    hit = matching_area(listing.kiez, listing.district, areas)
    if hit is not None:
        return (IN_AREA, hit, None)
    if listing.lat is None or listing.lng is None:
        return None
    near = nearest_area(listing.lat, listing.lng, areas)
    if near is None:
        return None
    name, km = near
    return (NEARBY if km <= NEARBY_MAX_KM else OUTSIDE, name, round(km, 1))


def _to_area_match_out(fit: AreaFit | None, kiez: str) -> AreaMatchOut | None:
    if fit is None:
        return None
    status, area, km = fit
    if status == IN_AREA:
        label = f"In {area}" if kiez == area else f"In {area} · {kiez}"
    elif status == NEARBY:
        label = f"Near {area} · {km:.1f} km"
    else:
        label = f"Outside your areas · {km:.1f} km from {area}"
    return AreaMatchOut(status=status, area=area, distance_km=km, label=label)


def _rank_criteria(criteria: SearchCriteria) -> RankCriteria:
    return RankCriteria(
        max_warm_rent=criteria.max_warm_rent,
        quiet_priority=criteria.quiet_priority,
        desired_amenities=tuple(criteria.desired_amenities),
        areas=tuple(criteria.areas),
    )


def _rank_input(
    listing: Listing,
    distance: float,
    fit: AreaFit | None,
    *,
    neighborhood=None,
    commute: CommuteResult | None = None,
) -> RankingInput:
    return RankingInput(
        warmmiete_eur=listing.warmmiete_eur,
        distance=distance,
        nightlife=_NIGHTLIFE.get(listing.kiez),
        available_amenities=neighborhood.available_amenities if neighborhood else None,
        commute_minutes=commute.minutes if commute else None,
        commute_source=commute.source if commute else "live",
        commute_changes=commute.changes if commute else None,
        listing_id=str(listing.id),
        kiez=listing.kiez,
        area_status=fit[0] if fit else None,
        area_name=fit[1] if fit else None,
        area_distance_km=fit[2] if fit else None,
    )


def _match_context(listing: Listing, criteria: SearchCriteria) -> MatchContext:
    return MatchContext(
        kiez=listing.kiez,
        rooms=float(listing.rooms) if listing.rooms is not None else None,
        size_m2=listing.size_m2,
        warm_rent=listing.warmmiete_eur,
        furnished=listing.furnished,
        asked_min_rooms=criteria.min_rooms,
        asked_min_size_m2=criteria.min_size_m2,
        asked_furnished=criteria.furnished,
    )


def _to_notice_out(notice: Notice) -> NoticeOut:
    return NoticeOut(**vars(notice))


# --- Empty-result handling: budget diagnosis + nearby fallback ----------------------------


def _diagnose(
    repo: ListingRepository, criteria: SearchCriteria, query: str, *, found: bool
) -> list[Notice]:
    """Explain missing results: is the budget the blocker, and what would fix it?"""
    budget = criteria.max_warm_rent
    if found and not (budget and criteria.areas):
        return []
    requirements = requirements_phrase(criteria.min_rooms, criteria.min_size_m2, criteria.furnished)

    # Everything matching the user's other requirements (same areas), at any price.
    relaxed = criteria.model_copy(update={"max_warm_rent": None})
    candidates = [r.listing for r in repo.retrieve(relaxed, query, limit=DIAGNOSIS_LIMIT)]
    risk = repo.risk_by_listing([x.id for x in candidates])
    # Never let a likely scam (often suspiciously cheap) set the recommended budget.
    trusted = [
        x for x in candidates if getattr(risk.get(str(x.id)), "band", None) != "high"
    ]

    if not found:
        if not candidates:
            if criteria.areas:
                return [no_listings_notice(criteria.areas, requirements)]
            return [no_results_notice(requirements)]
        advice = budget_advice(budget, [x.warmmiete_eur for x in trusted])
        return [budget_notice(advice, criteria.areas, requirements)] if advice else []

    # Results exist, but maybe some requested areas are entirely above budget.
    blocked: dict[str, int] = {}
    for area in criteria.areas:
        rents = [
            x.warmmiete_eur
            for x in trusted
            if matching_area(x.kiez, x.district, [area]) is not None
        ]
        if rents and min(rents) > budget:
            blocked[area] = min(rents)
    notice = partial_budget_notice(budget, blocked)
    return [notice] if notice else []


def _nearby_pool(
    repo: ListingRepository, criteria: SearchCriteria, query: str, size: int
) -> tuple[list[RetrievalResult], tuple[str, float] | None]:
    """Closest listings outside the requested areas (within NEARBY_MAX_KM), same filters.

    Also returns (Kiez, km) of the closest match beyond that radius, so an empty page
    can still point somewhere.
    """
    wide = criteria.model_copy(update={"areas": []})
    scored: list[tuple[float, RetrievalResult]] = []
    closest: tuple[str, float] | None = None
    for r in repo.retrieve(wide, query, limit=DIAGNOSIS_LIMIT):
        fit = _area_fit(r.listing, criteria.areas)
        if fit is None or fit[0] == IN_AREA:
            continue
        km = fit[2] or 0.0
        if fit[0] == NEARBY:
            scored.append((km, r))
        elif closest is None or km < closest[1]:
            closest = (r.listing.kiez, km)
    scored.sort(key=lambda pair: (pair[0], pair[1].distance))
    return [r for _, r in scored[:size]], closest


@router.post("/search", response_model=SearchResponse)
def search(
    req: SearchRequest, repo: ListingRepository = Depends(get_repository)
) -> SearchResponse:
    criteria = parse_query(req.query)
    if req.max_warm_rent is not None:
        criteria = criteria.model_copy(update={"max_warm_rent": req.max_warm_rent})
    rank_criteria = _rank_criteria(criteria)

    pool_size = max(req.limit * 3, 20)
    pool = repo.retrieve(criteria, req.query, limit=pool_size)
    notices = _diagnose(repo, criteria, req.query, found=bool(pool))
    if not pool and criteria.areas:
        # Nothing inside the requested areas: show the closest matches, clearly labelled.
        pool, closest = _nearby_pool(repo, criteria, req.query, pool_size)
        kinds = {n.kind for n in notices}
        # The nearby notice says "no listings in X" itself; don't show it twice.
        notices = [n for n in notices if n.kind != NO_LISTINGS_IN_AREA]
        if pool or BUDGET_TOO_LOW not in kinds:  # the budget hint explains an empty page
            notices.append(
                nearby_notice(
                    criteria.areas,
                    len(pool),
                    NEARBY_MAX_KM,
                    none_in_area=NO_LISTINGS_IN_AREA in kinds,
                    requirements=requirements_phrase(
                        criteria.min_rooms, criteria.min_size_m2, criteria.furnished
                    ),
                    closest=closest,
                )
            )
    elif not pool and not notices:
        notices.append(
            no_results_notice(
                requirements_phrase(criteria.min_rooms, criteria.min_size_m2, criteria.furnished)
            )
        )

    listings_by_id = {str(r.listing.id): r.listing for r in pool}
    distance_by_id = {str(r.listing.id): r.distance for r in pool}
    fit_by_id = {str(r.listing.id): _area_fit(r.listing, criteria.areas) for r in pool}

    # Pass 1 — cheap factors (relevance, area, budget, quiet-from-Kiez) to pick the page.
    cheap_inputs = [
        _rank_input(r.listing, r.distance, fit_by_id[str(r.listing.id)]) for r in pool
    ]
    page = rank(cheap_inputs, rank_criteria)[: req.limit]

    # Pass 2 — enrich just the page (commute + neighborhood), then re-rank.
    commute_by_id = {}
    neighborhood_by_id = {}
    enriched_inputs: list[RankingInput] = []
    for inp, _ in page:
        listing = listings_by_id[inp.listing_id]
        neighborhood = repo.neighborhood(listing.lat, listing.lng)
        commute = repo.commute(listing.lat, listing.lng, criteria.work_location)
        if neighborhood is not None:
            neighborhood_by_id[inp.listing_id] = neighborhood
        if commute is not None:
            commute_by_id[inp.listing_id] = commute
        enriched_inputs.append(
            _rank_input(
                listing,
                distance_by_id[inp.listing_id],
                fit_by_id[inp.listing_id],
                neighborhood=neighborhood,
                commute=commute,
            )
        )
    ranked = rank(enriched_inputs, rank_criteria)

    page_listings = [listings_by_id[i.listing_id] for i, _ in ranked]
    photos_by_set = repo.photos_by_set([x.photo_set_id for x in page_listings])
    risk_by_id = repo.risk_by_listing([x.id for x in page_listings])

    results: list[SearchResultItem] = []
    for inp, result in ranked:
        listing = listings_by_id[inp.listing_id]
        commute = commute_by_id.get(inp.listing_id)
        neighborhood = neighborhood_by_id.get(inp.listing_id)
        results.append(
            SearchResultItem(
                listing=_to_listing_out(listing, photos_by_set.get(listing.photo_set_id, [])),
                score=round(result.total, 4),
                factors=[FactorOut(**vars(f)) for f in result.factors],
                explanation=explain(result, context=_match_context(listing, criteria)),
                risk=_to_risk_out(risk_by_id.get(inp.listing_id)),
                commute=_to_commute_out(commute),
                neighborhood=(
                    NeighborhoodOut(summary=neighborhood.summary, counts=neighborhood.counts)
                    if neighborhood
                    else None
                ),
                area_match=_to_area_match_out(fit_by_id[inp.listing_id], listing.kiez),
            )
        )

    # Privacy (ADR-0012): never log the query text or parsed values (budget, work
    # location, areas, …) — only which fields were understood, how many results we
    # returned and which kinds of notice were shown.
    logger.info(
        "search results=%d parsed_fields=%s notices=%s",
        len(results),
        sorted(k for k, v in criteria.model_dump().items() if v not in (None, False, [], "")),
        [n.kind for n in notices],
    )
    commute_note = _commute_note(
        criteria.work_location, [commute_by_id.get(i.listing_id) for i, _ in ranked]
    )
    return SearchResponse(
        criteria=criteria,
        results=results,
        commute_note=commute_note,
        notices=[_to_notice_out(n) for n in notices],
    )


# --- Listing detail (T5.1) ------------------------------------------------------


class PoiOut(BaseModel):
    category: str
    name: str
    lat: float
    lng: float


class ListingDetailOut(BaseModel):
    id: str
    title: str
    description: str
    address: str
    kiez: str
    district: str | None
    lat: float
    lng: float
    rooms: float
    size_m2: int
    kaltmiete_eur: int
    nebenkosten_eur: int
    warmmiete_eur: int
    deposit_eur: int | None
    furnished: bool
    available_from: date | None
    floor: int | None
    total_floors: int | None
    anmeldung_possible: bool
    photos: list[PhotoOut] = Field(default_factory=list)
    year_built: int | None = None


class NeighborhoodDetailOut(BaseModel):
    summary: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    pois: list[PoiOut] = Field(default_factory=list)
    # Radius the amenities were searched in (drawn on the map when tiles are offline).
    radius_m: int = DEFAULT_RADIUS_M


class ListingDetailResponse(BaseModel):
    listing: ListingDetailOut
    risk: RiskOut | None = None
    neighborhood: NeighborhoodDetailOut | None = None
    location: ListingLocationOut | None = None
    rent: RentOut | None = None


class MapListingOut(BaseModel):
    """Just what the homepage map needs: a point, a price and the card details."""

    id: str
    title: str
    kiez: str
    district: str | None
    lat: float
    lng: float
    rooms: float
    size_m2: int
    warmmiete_eur: int
    photo_url: str | None = None  # cover photo (first of the set)
    risk_band: str | None = None  # low | caution | high
    # Berlin data (ADR-0016/0017): for the Explore Berlin cards that follow the map.
    rent_verdict: str | None = None
    rail_stop: str | None = None
    rail_modes: list[str] = Field(default_factory=list)
    rail_walk_minutes: int | None = None


# Every listing inside Berlin; the map aggregates medians client-side from these.
MAP_LISTINGS_LIMIT = 2000


@router.get("/listings/map", response_model=list[MapListingOut])
def get_map_listings(repo: ListingRepository = Depends(get_repository)) -> list[MapListingOut]:
    """All available listings as map points (declared before /listings/{listing_id})."""
    rows = repo.listings_in_bbox(
        BERLIN_BBOX["lat_min"],
        BERLIN_BBOX["lng_min"],
        BERLIN_BBOX["lat_max"],
        BERLIN_BBOX["lng_max"],
        limit=MAP_LISTINGS_LIMIT,
    )
    if not rows:
        return []
    photos_by_set = repo.photos_by_set([x.photo_set_id for x in rows])
    risk_by_id = repo.risk_by_listing([x.id for x in rows])
    out: list[MapListingOut] = []
    for x in rows:
        photos = photos_by_set.get(x.photo_set_id, [])
        risk = risk_by_id.get(str(x.id))
        out.append(
            MapListingOut(
                id=str(x.id),
                title=x.title,
                kiez=x.kiez,
                district=x.district,
                **(
                    {"lat": x.lat, "lng": x.lng}
                    | _map_berlin_fields(x)
                    | {
                        "rooms": float(x.rooms),
                        "size_m2": x.size_m2,
                        "warmmiete_eur": x.warmmiete_eur,
                        "photo_url": photos[0].source_url if photos else None,
                        "risk_band": risk.band if risk else None,
                    }
                ),
            )
        )
    return out


def _map_berlin_fields(listing: Listing) -> dict:
    fields = _berlin_fields(listing)
    out: dict = {}
    if "rent" in fields:
        out["rent_verdict"] = fields["rent"].verdict
    if "location" in fields:
        loc = fields["location"]
        out |= {
            "lat": loc.lat,  # same point as the listing page and the results map
            "lng": loc.lng,
            "rail_stop": loc.rail_stop,
            "rail_modes": loc.rail_modes,
            "rail_walk_minutes": loc.rail_walk_minutes,
        }
    return out


@router.get("/listings/random", response_model=list[ListingOut])
def get_random_listings(
    n: int = 6, repo: ListingRepository = Depends(get_repository)
) -> list[ListingOut]:
    rows = repo.random_listings(n)
    if not rows:
        return []
    photos_by_set = repo.photos_by_set([x.photo_set_id for x in rows])
    return [_to_listing_out(listing, photos_by_set.get(listing.photo_set_id, [])) for listing in rows]


@router.get("/listings/{listing_id}", response_model=ListingDetailResponse)
def get_listing(
    listing_id: str, repo: ListingRepository = Depends(get_repository)
) -> ListingDetailResponse:
    try:
        uid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id") from None

    listing = repo.get_listing(uid)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    photos_by_set = repo.photos_by_set([listing.photo_set_id])
    photos = photos_by_set.get(listing.photo_set_id, [])
    risk_by_id = repo.risk_by_listing([listing.id])
    neighborhood = repo.neighborhood(listing.lat, listing.lng, cache_only=True)

    neighborhood_detail: NeighborhoodDetailOut | None = None
    if neighborhood is not None:
        pois = [
            PoiOut(
                category=p.get("category") or "",
                name=p.get("name") or "",
                lat=float(p.get("lat") or 0),
                lng=float(p.get("lng") or 0),
            )
            for p in neighborhood.pois
        ]
        neighborhood_detail = NeighborhoodDetailOut(
            summary=neighborhood.summary,
            counts=neighborhood.counts,
            pois=pois,
        )

    return ListingDetailResponse(
        listing=ListingDetailOut(
            id=str(listing.id),
            title=listing.title,
            description=listing.description,
            address=listing.address,
            kiez=listing.kiez,
            district=listing.district,
            lat=listing.lat,
            lng=listing.lng,
            rooms=float(listing.rooms),
            size_m2=listing.size_m2,
            kaltmiete_eur=listing.kaltmiete_eur,
            nebenkosten_eur=listing.nebenkosten_eur,
            warmmiete_eur=listing.warmmiete_eur,
            deposit_eur=listing.deposit_eur,
            furnished=listing.furnished,
            available_from=listing.available_from,
            floor=listing.floor,
            total_floors=listing.total_floors,
            anmeldung_possible=listing.anmeldung_possible,
            photos=[
                PhotoOut(url=p.source_url, room_type=p.room_type, attribution=p.attribution)
                for p in photos
            ],
            year_built=listing.year_built,
        ),
        risk=_to_risk_out(risk_by_id.get(str(listing.id))),
        neighborhood=neighborhood_detail,
        **_berlin_fields(listing),
    )


class ListingCommuteOut(BaseModel):
    to: str
    commute: CommuteOut | None = None
    note: str | None = None


@router.get("/listings/{listing_id}/commute", response_model=ListingCommuteOut)
def get_listing_commute(
    listing_id: str,
    repo: Annotated[ListingRepository, Depends(get_repository)],
    to: str = Query(min_length=2, max_length=80),
) -> ListingCommuteOut:
    """Trip time from the listing to a place the user types (live BVG, else an estimate).

    Measured from the matched address, like the rest of the page. The place name is used
    for this request only and isn't logged (ADR-0012).
    """
    try:
        uid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id") from None
    listing = repo.get_listing(uid)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    lat, lng = listing.lat, listing.lng
    loc = _berlin_fields(listing).get("location")
    if loc is not None and loc.lat is not None:
        lat, lng = loc.lat, loc.lng
    place = to.strip()
    result = repo.commute(lat, lng, place)
    return ListingCommuteOut(
        to=place, commute=_to_commute_out(result), note=_commute_note(place, [result])
    )


class SimilarItemOut(BaseModel):
    listing: ListingOut
    risk: RiskOut | None = None
    score: float  # 0..1, from named factors (search/similar.py)
    distance_km: float
    reasons: list[str]


class SimilarResponse(BaseModel):
    # True when this flat is above the rent-brake limit and flats within it come first.
    within_limit_first: bool
    items: list[SimilarItemOut]


SIMILAR_LIMIT = 12


def _similar_flat(listing: Listing, fields: dict) -> SimilarFlat:
    loc = fields.get("location")
    rent = fields.get("rent")
    return SimilarFlat(
        id=str(listing.id),
        lat=loc.lat if loc and loc.lat is not None else listing.lat,
        lng=loc.lng if loc and loc.lng is not None else listing.lng,
        rooms=float(listing.rooms),
        size_m2=listing.size_m2,
        warm_eur=listing.warmmiete_eur,
        furnished=listing.furnished,
        planning_area=loc.planning_area if loc else None,
        district=listing.district,
        period=rent.period if rent else None,
        rent_verdict=rent.verdict if rent else None,
        photo_set_id=str(listing.photo_set_id) if listing.photo_set_id else None,
    )


@router.get("/listings/{listing_id}/similar", response_model=SimilarResponse)
def get_similar_listings(
    listing_id: str, repo: Annotated[ListingRepository, Depends(get_repository)]
) -> SimilarResponse:
    """Similar flats, ranked deterministically with a reason per card (T9.7). High-risk
    listings are included and carry their risk; copies reusing the photos are left out."""
    try:
        uid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id") from None
    target = repo.get_listing(uid)
    if target is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    pool = repo.listings_in_bbox(
        BERLIN_BBOX["lat_min"],
        BERLIN_BBOX["lng_min"],
        BERLIN_BBOX["lat_max"],
        BERLIN_BBOX["lng_max"],
        limit=MAP_LISTINGS_LIMIT,
    )
    fields = {str(x.id): _berlin_fields(x) for x in pool}
    target_fields = fields.get(str(target.id)) or _berlin_fields(target)
    ranked, fair_first = rank_similar(
        _similar_flat(target, target_fields),
        [_similar_flat(x, fields[str(x.id)]) for x in pool],
        limit=SIMILAR_LIMIT,
    )
    by_id = {str(x.id): x for x in pool}
    chosen = [by_id[s.id] for s in ranked]
    photos_by_set = repo.photos_by_set([x.photo_set_id for x in chosen])
    risk_by_id = repo.risk_by_listing([x.id for x in chosen])
    items = []
    for s, x in zip(ranked, chosen, strict=True):
        out = _to_listing_out(x, photos_by_set.get(x.photo_set_id, []))
        items.append(
            SimilarItemOut(
                listing=out,
                risk=_to_risk_out(risk_by_id.get(s.id)),
                score=s.score,
                distance_km=s.distance_km,
                reasons=s.reasons,
            )
        )
    return SimilarResponse(within_limit_first=fair_first, items=items)


@router.get("/listings/{listing_id}/around")
def get_listing_around(
    listing_id: str, repo: Annotated[ListingRepository, Depends(get_repository)]
) -> dict:
    """Around this flat: the place profile at the listing, with its matched location class."""
    from berlin import get_berlin_data
    from berlin.files import BuildMissing
    from berlin.listings import listing_location
    from berlin.profile import build_profile

    try:
        uid = uuid.UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id") from None
    listing = repo.get_listing(uid)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    try:
        data = get_berlin_data()
    except BuildMissing:
        raise HTTPException(status_code=503, detail="Berlin data not built") from None
    location = listing_location(data, listing)
    if location is None:
        return build_profile(data, listing.lat, listing.lng).to_dict()
    # Measured at the matched address, like the location and rent (one point, one story).
    return build_profile(data, location.lat, location.lng, location.location_class).to_dict()


# --- Comparison (F8) ------------------------------------------------------------
# Side-by-side of 2–4 listings. Reuses the exact same helpers as /search
# (_to_listing_out, enrichment, score_listing, explain) so the compared fields can't
# drift from what search shows (SPEC F8 AC1).


class CompareRequest(BaseModel):
    listing_ids: list[str] = Field(min_length=2, max_length=4)
    query: str | None = None  # optional context for fit + commute


class ComparisonItem(BaseModel):
    listing: ListingOut
    fit_score: float | None = None
    factors: list[FactorOut] = Field(default_factory=list)
    explanation: Explanation | None = None
    commute: CommuteOut | None = None
    neighborhood: NeighborhoodOut | None = None
    risk: RiskOut | None = None


class CompareResponse(BaseModel):
    criteria: SearchCriteria | None = None
    items: list[ComparisonItem]


@router.post("/compare", response_model=CompareResponse)
def compare(
    req: CompareRequest, repo: ListingRepository = Depends(get_repository)
) -> CompareResponse:
    try:
        ids = [uuid.UUID(x) for x in req.listing_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid listing id") from None

    found = {str(x.id): x for x in repo.get_listings(ids)}
    missing = [x for x in req.listing_ids if x not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Listing(s) not found: {missing}")
    ordered = [found[x] for x in req.listing_ids]  # preserve requested order

    criteria = parse_query(req.query) if req.query else None
    rank_criteria = _rank_criteria(criteria) if criteria else None
    photos_by_set = repo.photos_by_set([x.photo_set_id for x in ordered])
    risk_by_id = repo.risk_by_listing([x.id for x in ordered])

    items: list[ComparisonItem] = []
    for listing in ordered:
        neighborhood = repo.neighborhood(listing.lat, listing.lng)
        commute = (
            repo.commute(listing.lat, listing.lng, criteria.work_location)
            if criteria
            else None
        )

        fit_score: float | None = None
        factors: list[FactorOut] = []
        explanation: Explanation | None = None
        if rank_criteria is not None and criteria is not None:
            result = score_listing(
                _rank_input(
                    listing,
                    0.0,  # no per-listing query vector here; relevance is constant
                    _area_fit(listing, criteria.areas),
                    neighborhood=neighborhood,
                    commute=commute,
                ),
                rank_criteria,
            )
            fit_score = round(result.total, 4)
            factors = [FactorOut(**vars(f)) for f in result.factors]
            explanation = explain(result, context=_match_context(listing, criteria))

        items.append(
            ComparisonItem(
                listing=_to_listing_out(listing, photos_by_set.get(listing.photo_set_id, [])),
                fit_score=fit_score,
                factors=factors,
                explanation=explanation,
                commute=_to_commute_out(commute),
                neighborhood=(
                    NeighborhoodOut(summary=neighborhood.summary, counts=neighborhood.counts)
                    if neighborhood
                    else None
                ),
                risk=_to_risk_out(risk_by_id.get(str(listing.id))),
            )
        )

    return CompareResponse(criteria=criteria, items=items)
