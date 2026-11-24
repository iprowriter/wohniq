"""Around this flat: eight measures for any point in Berlin, each placed among Berlin's areas.

Every card carries its source label, a headline, a position (0–100) for the bar, one neutral
comparison sentence and a detail line, all built from data values (golden rule 3). Areas are
described, never judged (design rule): the wording says "closer/farther", "more/fewer",
"higher/lower", never "better/worse", and nothing here feeds ranking.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from berlin.measures import gather_point, measures_from
from berlin.repository import BerlinData, Stop
from enrich.commute_estimate import walk_minutes

N_AREAS = 542
N_REGIONS = 143
LQI_LABELS = {
    1: "very good",
    2: "good",
    3: "satisfactory",
    4: "sufficient",
    5: "poor",
    6: "very poor",
}
SCHOOL_KIND_ORDER = (
    ("primary", "primary"),
    ("secondary", "secondary"),
    ("vocational", "vocational"),
    ("special", "special needs"),
)
CLASS_POSITION = {"simple": 1, "medium": 2, "good": 3}
CLASS_LABEL = {"simple": "Simple", "medium": "Medium", "good": "Good"}


@dataclass
class Measure:
    key: str
    label: str
    source: str
    headline: str
    position: float  # 0–100, where this point sits (bar length)
    comparison: str
    detail: str
    value: float | None = None


@dataclass
class PlaceProfile:
    lat: float
    lng: float
    planning_area: str | None
    district_region: str | None
    district: str | None
    measures: list[Measure]

    def to_dict(self) -> dict:
        return asdict(self)


def walk_min(distance_m: float) -> int:
    """Walking minutes (straight line × detour at walking speed, enrich/commute_estimate)."""
    return max(1, math.ceil(walk_minutes(distance_m / 1000)))


def _share(values: list[float], pred) -> int:
    return round(100 * sum(1 for v in values if pred(v)) / len(values)) if values else 0


def distance_sentence(value: float, values: list[float], n: int = N_AREAS) -> tuple[str, float]:
    closer = _share(values, lambda v: v > value)
    if closer >= 50:
        return f"Closer than {closer}% of Berlin's {n} planning areas", closer
    farther = _share(values, lambda v: v < value)
    return f"Farther than {farther}% of Berlin's {n} planning areas", closer


def count_sentence(value: float, values: list[float], n: int = N_AREAS) -> tuple[str, float]:
    more = _share(values, lambda v: v < value)
    if more >= 50:
        return f"More than in {more}% of Berlin's {n} planning areas", more
    fewer = _share(values, lambda v: v > value)
    if fewer == 0:
        return f"About the same as most of Berlin's {n} planning areas", more
    return f"Fewer than in {fewer}% of Berlin's {n} planning areas", more


def _stat_values(stats: dict[str, dict[str, float]], key: str) -> list[float]:
    return [s[key] for s in stats.values() if key in s]


def stop_label(stop: Stop) -> str:
    return stop.name


def build_profile(
    data: BerlinData, lat: float, lng: float, location_class: str | None = None
) -> PlaceProfile:
    stats = data.area_stats()
    facts = gather_point(data, lat, lng)
    area = facts.area
    m = measures_from(facts)
    out: list[Measure] = []

    # 1 Nearest S/U-Bahn
    if facts.rail:
        s = facts.rail
        sentence, pos = distance_sentence(s.distance_m, _stat_values(stats, "rail_stop_m"))
        out.append(
            Measure(
                "rail",
                "Nearest S/U-Bahn",
                "VBB",
                f"{s.name} · {walk_min(s.distance_m)} min walk",
                pos,
                sentence,
                f"{round(s.distance_m)} m in a straight line; walking time estimated",
                round(s.distance_m),
            )
        )

    # 2 Schools within 1 km (adult education left out)
    schools = facts.schools
    sentence, pos = count_sentence(len(schools), _stat_values(stats, "schools_1km"))
    kinds = [
        f"{sum(1 for x in schools if x['kind'] == k)} {label}"
        for k, label in SCHOOL_KIND_ORDER
        if any(x["kind"] == k for x in schools)
    ]
    out.append(
        Measure(
            "schools",
            "Schools within 1 km",
            "Senate",
            f"{len(schools)} school{'s' if len(schools) != 1 else ''}",
            pos,
            sentence,
            ", ".join(kinds) if kinds else "No school within 1 km",
            len(schools),
        )
    )

    # 3 Kitas within 500 m (compared by permitted places)
    places = m["kita_places_500m"]
    sentence, pos = count_sentence(places, _stat_values(stats, "kita_places_500m"))
    n_kitas = int(m["kitas_500m"])
    out.append(
        Measure(
            "kitas",
            "Kitas within 500 m",
            "Senate",
            f"{n_kitas} Kita{'s' if n_kitas != 1 else ''} · {int(places):,} places",
            pos,
            sentence,
            "Permitted places, Kita list of November 2025",
            places,
        )
    )

    # 4 Parks and playgrounds (compared by distance to the nearest green space ≥ 1 ha)
    park = facts.park
    playgrounds = int(m["playgrounds_500m"])
    if park:
        sentence, pos = distance_sentence(park.distance_m, _stat_values(stats, "park_m"))
        where = "inside" if park.distance_m == 0 else f"{round(park.distance_m)} m"
        out.append(
            Measure(
                "green",
                "Parks and playgrounds",
                "Geoportal",
                f"{park.name} {where} · {playgrounds} playground{'s' if playgrounds != 1 else ''}",
                pos,
                sentence,
                f"Nearest green space of 1 ha or more ({park.area_m2 / 10_000:.1f} ha); "
                "playgrounds within 500 m",
                round(park.distance_m),
            )
        )

    # 5 Air quality (nearest station, latest snapshot)
    air = facts.air
    if air and air.lqi is not None:
        when = (air.measured_at or "")[:16].replace("T", ", ")
        out.append(
            Measure(
                "air",
                "Air quality",
                "luftdaten.berlin",
                f"Index {air.lqi} · {LQI_LABELS.get(air.lqi, '')}",
                round(100 * air.lqi / 6),
                "Berlin's index runs from 1 (very good) to 6 (very poor)",
                f"Station {air.name} ({air.station_type}), {air.distance_m / 1000:.1f} km away · "
                f"snapshot {when}",
                air.lqi,
            )
        )

    # 6 Road accidents within 300 m
    accidents = facts.accidents
    sentence, pos = count_sentence(len(accidents), _stat_values(stats, "accidents_300m"))
    severe = sum(1 for a in accidents if a["category"] <= 2)
    vulnerable = sum(1 for a in accidents if a["bike"] or a["pedestrian"])
    out.append(
        Measure(
            "accidents",
            "Road accidents nearby",
            "Unfallatlas",
            f"{len(accidents)} within 300 m (2025)",
            pos,
            sentence,
            f"Accidents with injuries; {severe} with someone killed or seriously injured, "
            f"{vulnerable} involving a cyclist or pedestrian",
            len(accidents),
        )
    )

    # 7 Recorded crime (district region level only)
    if area is not None:
        rate = data.crime(area.bzr_id)
        rates = list(data.crime_rates().values())
        if rate is not None and rates:
            higher = _share(rates, lambda v: v < rate)
            sentence = (
                f"Higher than in {higher}% of Berlin's {N_REGIONS} district regions"
                if higher >= 50
                else f"Lower than in {_share(rates, lambda v: v > rate)}% of Berlin's "
                f"{N_REGIONS} district regions"
            )
            out.append(
                Measure(
                    "crime",
                    "Recorded crime",
                    "Police atlas",
                    f"District region {area.bzr_name}",
                    higher,
                    sentence,
                    f"{rate:,.0f} neighbourhood offences (Kieztaten) per 100,000 residents a year, "
                    "2023–2025. Busy centres read higher: many visitors, few residents.",
                    rate,
                )
            )

    # 8 Location class (rent index)
    cls = location_class
    if cls is None:
        near = data.nearest_address(lat, lng)
        cls = near.location_class if near else None
    if cls:
        share = data.location_class_share(lat, lng, 300).get(cls, 0)
        out.append(
            Measure(
                "location_class",
                "Location class",
                "Mietspiegel",
                f"{CLASS_LABEL[cls]} (rent index)",
                round(100 * CLASS_POSITION[cls] / 3),
                "Simple · medium · good",
                f"Used by the Mietspiegel; {round(100 * share)}% of the addresses within 300 m "
                "have the same class",
                CLASS_POSITION[cls],
            )
        )

    return PlaceProfile(
        lat,
        lng,
        area.plr_name if area else None,
        area.bzr_name if area else None,
        area.district if area else None,
        out,
    )
