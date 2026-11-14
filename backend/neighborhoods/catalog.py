"""What Berlin Neighbourhoods measures: categories and the metrics inside them.

The single source of truth for labels, units, direction ("is higher better?") and the
weights that combine metrics into a category score. The data build writes raw values
under these ids; the API and UI read labels from here, so they can't drift.

A metric with `requires` is *pending*: it is part of the design, but the data hasn't been
supplied yet. It's listed in the catalogue (the UI shows "coming when data arrives") and
is never scored. Availability is derived from the bundle: a metric is available iff
the bundle has a reference distribution for it.

Wording rules (ADR-0013): ranking labels describe the measure ("Lowest crime",
"Higher social status"), never the people living there, and no category tells users
to "avoid" an area.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Format = Literal["int", "dec1", "dec2", "pct", "metres", "minutes", "class", "eur_m2"]
Level = Literal["region", "district"]


@dataclass(frozen=True)
class Metric:
    id: str
    category: str
    label: str
    unit: str  # shown after the number
    higher_is_better: bool
    weight: float  # within its category; 0 = shown for context, not scored
    fmt: Format
    description: str
    level: Level = "region"  # "district": one value per district (all its areas share it)
    # No per-area data: why (e.g. "Not published per neighborhood"). Listed, never scored.
    requires: str | None = None


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    emoji: str
    question: str  # what ranking by this category answers
    best_label: str  # tier badge for the top 20%
    worst_label: str  # tier badge for the bottom 20%
    default_weight: int  # in the overall score (0–3)
    caveat: str


CATEGORIES: tuple[Category, ...] = (
    Category(
        "safety",
        "Safety",
        "🛡️",
        "Where is reported crime lowest?",
        "Lowest crime",
        "Highest crime",
        2,
        "Police-recorded offences per 100,000 residents, averaged over 2023–2025. Areas many "
        "people visit (centre, nightlife, stations) read higher than what residents experience; "
        "the police note a high rate can also reflect liveliness. Unreported crime isn't included.",
    ),
    Category(
        "road_safety",
        "Road safety",
        "🚦",
        "Where do the fewest road accidents happen?",
        "Fewest accidents",
        "Most accidents",
        1,
        "Accidents with personal injury recorded by the police in 2025, per 10 km of public "
        "street. Main roads carry through traffic, so their accidents count where they happen, "
        "not where the people involved live.",
    ),
    Category(
        "affluence",
        "Affluence",
        "💶",
        "Which areas have the highest social and economic status?",
        "Highest status",
        "Lowest status",
        1,
        "A proxy, not a measure of wealth: median wealth and income aren't published for "
        "neighbourhoods in Germany. We combine the Senate's social-status index (built from "
        "indicators such as unemployment and welfare receipt) with official land values at "
        "residents' homes. Both describe places, not any person, and areas change.",
    ),
    Category(
        "education",
        "Education",
        "🎓",
        "Where are school results strongest and schools closest?",
        "Strongest education",
        "Weakest education",
        1,
        "Literacy isn't published below national level. School results (Abitur share, leavers "
        "without a qualification, Gymnasium recommendations) are per district and counted where "
        "the school is, so all areas of a district share them; nearby schools and Kitas are "
        "measured from homes (OpenStreetMap).",
    ),
    Category(
        "health",
        "Healthcare",
        "🏥",
        "Where are hospitals, doctors and pharmacies closest?",
        "Best healthcare access",
        "Weakest healthcare access",
        1,
        "Mapped in OpenStreetMap: hospitals include specialist clinics; doctors include "
        "dentists and clinics. Straight-line distances from homes.",
    ),
    Category(
        "amenities",
        "Amenities",
        "☕",
        "Where are cafés, shops, culture and sport within walking distance?",
        "Most amenities",
        "Fewest amenities",
        1,
        "Counted from OpenStreetMap within walking distance of homes. Nightlife is shown but "
        "not scored — whether it's a plus depends on you.",
    ),
    Category(
        "green",
        "Parks & nature",
        "🌳",
        "Where are parks, water and forest closest?",
        "Greenest",
        "Least green",
        1,
        "Green-space supply from the Senate's environmental-justice atlas (data from 2020); "
        "park, water and forest distances and playgrounds from OpenStreetMap.",
    ),
    Category(
        "transit",
        "Public transport",
        "🚇",
        "Where are S-/U-Bahn, tram and bus closest and the centre quickest to reach?",
        "Best connected",
        "Least connected",
        1,
        "Rail and tram stops with weekday-peak service (VBB timetable); all stops from "
        "OpenStreetMap; travel time to Alexanderplatz routed over the VBB timetable.",
    ),
    Category(
        "environment",
        "Quiet & clean air",
        "🍃",
        "Where is traffic noise, air pollution and summer heat lowest?",
        "Quietest & cleanest",
        "Noisiest & most polluted",
        1,
        "Berlin-relative classes from the environmental-justice atlas 2023/24 (noise 2022, "
        "air 2023, heat 2022), weighted by where residents live. Not absolute health limits.",
    ),
    Category(
        "parking",
        "Parking",
        "🅿️",
        "Where is it easiest to park a car?",
        "Easiest parking",
        "Hardest parking",
        1,
        "Paid-parking streets are detected from parking ticket machines mapped in "
        "OpenStreetMap; car-park areas are as complete as OSM mapping. Density stands in for "
        "parking pressure. On-street spaces aren't counted anywhere officially.",
    ),
    Category(
        "affordability",
        "Affordability",
        "🏷️",
        "Where are asking rents lowest?",
        "Most affordable",
        "Least affordable",
        1,
        "Median asking rent of the district (IBB 2025), so all areas of a district share it. "
        "80% of offers fall within the district's range shown with each area.",
    ),
)

CATEGORIES_BY_ID = {c.id: c for c in CATEGORIES}


def _m(*args, **kwargs) -> Metric:
    return Metric(*args, **kwargs)


PER_100K = "per 100,000 residents"
PER_10KM = "per 10 km of street"

# fmt: off
METRICS: tuple[Metric, ...] = (
    # --- Safety (Kriminalitätsatlas, mean 2023–2025) ---
    _m("crime_kiez", "safety", "Neighbourhood offences", PER_100K, False, 3, "int",
       "‘Kieztaten’: the police's neighbourhood-related offences — e.g. assault, threats, "
       "robbery, burglary, vandalism of cars."),
    _m("crime_violence", "safety", "Assaults", PER_100K, False, 2, "int",
       "Bodily harm, all kinds."),
    _m("crime_robbery", "safety", "Robbery", PER_100K, False, 1, "int",
       "Robbery, incl. street and handbag robbery."),
    _m("crime_burglary", "safety", "Home burglary", PER_100K, False, 1, "int",
       "Break-ins into homes."),
    _m("crime_total", "safety", "All reported offences", PER_100K, False, 1, "int",
       "Every offence recorded in the area, incl. those against visitors and businesses."),
    _m("crime_bike_theft", "safety", "Bike theft", PER_100K, False, 0.5, "int",
       "Bicycles stolen."),
    _m("crime_car", "safety", "Car theft & break-ins", PER_100K, False, 0.5, "int",
       "Cars stolen plus thefts from or of parts of cars."),
    # --- Road safety (Unfallatlas 2025) ---
    _m("accidents", "road_safety", "Injury accidents", PER_10KM, False, 2, "dec1",
       "Road accidents in which someone was hurt."),
    _m("accidents_severe", "road_safety", "Killed or seriously injured", PER_10KM, False, 2,
       "dec1", "Accidents in which someone died or was seriously injured."),
    _m("accidents_vulnerable", "road_safety", "Involving pedestrians or cyclists", PER_10KM,
       False, 1, "dec1", "Injury accidents in which a pedestrian or cyclist was involved."),
    # --- Affluence ---
    _m("social_status", "affluence", "Social-status index", "class, 1 high – 4 very low", False,
       2, "dec2", "Monitoring Soziale Stadtentwicklung 2023: the Senate's status class of each "
       "planning area, weighted by its residents."),
    _m("land_value", "affluence", "Land-value index", "0–100, vs. land of the same density",
       True, 2, "int", "Where the standard land values (Bodenrichtwerte 2026) at the area's homes "
       "rank among Berlin's residential zones of the same kind — houses compared with houses, "
       "blocks of flats with flats. 100 = Berlin's priciest land of its kind."),
    _m("land_value_eur", "affluence", "Typical land value", "EUR/m² of plot, median at homes",
       True, 0, "int", "Median Bodenrichtwert at the area's homes (context, not scored: it "
       "mostly reflects how densely land may be built on)."),
    _m("income", "affluence", "Income per taxpayer", "EUR per year", True, 2, "int",
       "Total income per taxpayer from the income-tax statistics.", level="district",
       requires="Not published per neighborhood"),
    # --- Education ---
    _m("edu_abitur", "education", "School leavers with Abitur", "% of leavers", True, 2, "pct",
       "Share of leavers from general schools in the district with the Abitur, 2024/25.",
       level="district"),
    _m("edu_no_qualification", "education", "Leavers without a qualification", "% of leavers",
       False, 1, "pct", "Share leaving general schools without the Berufsbildungsreife, 2024/25.",
       level="district"),
    _m("edu_gymnasium", "education", "Gymnasium recommendations", "% of primary leavers", True, 1,
       "pct", "Primary pupils with a Gymnasium/ISS recommendation (Förderprognose), 2024/25.",
       level="district"),
    _m("schools", "education", "Schools within 1 km", "schools", True, 1, "dec1",
       "Schools within 1 km of the typical home."),
    _m("kitas", "education", "Kitas within 500 m", "day-care centres", True, 1, "dec1",
       "Kitas (day-care centres) within 500 m of the typical home."),
    # --- Healthcare ---
    _m("hospital_distance", "health", "Nearest hospital", "straight line", False, 2, "metres",
       "Distance from the typical home to the nearest hospital."),
    _m("doctors", "health", "Doctors within 1 km", "doctors, dentists, clinics", True, 2, "dec1",
       "Doctors, dentists and clinics within 1 km of the typical home."),
    _m("pharmacies", "health", "Pharmacies within 500 m", "pharmacies", True, 1, "dec1",
       "Pharmacies within 500 m of the typical home."),
    # --- Amenities (Lifestyle Match figures) ---
    _m("cafes", "amenities", "Cafés & restaurants within 500 m", "places", True, 2, "dec1",
       "Cafés, restaurants and bakeries within 500 m of the typical home."),
    _m("everyday", "amenities", "Everyday shops within 500 m", "shops", True, 2, "dec1",
       "Supermarkets, pharmacies and doctors within 500 m of the typical home."),
    _m("culture", "amenities", "Culture within 1.5 km", "venues", True, 1, "dec1",
       "Museums, theatres, cinemas, arts centres and libraries within 1.5 km."),
    _m("sport", "amenities", "Sport within 1 km", "venues", True, 1, "dec1",
       "Gyms, pools and sports centres within 1 km."),
    _m("nightlife", "amenities", "Bars & clubs within 1 km", "venues", True, 0, "dec1",
       "Bars, pubs, clubs and beer gardens within 1 km (context only, not scored)."),
    # --- Parks & nature ---
    _m("green_supply", "green", "Green-space supply", "class, 1 good – 3 poor", False, 2, "dec2",
       "Public green space per resident, Berlin-relative class, weighted by residents."),
    _m("park_distance", "green", "Nearest park (≥ 1 ha)", "straight line", False, 2, "metres",
       "Distance from the typical home to the edge of a public park of at least 1 ha."),
    _m("water_forest", "green", "Nearest water or forest", "straight line", False, 1, "metres",
       "Distance to the nearest lake, river or canal (≥ 1 ha) or forest (≥ 5 ha)."),
    _m("playgrounds", "green", "Playgrounds within 500 m", "playgrounds", True, 1, "dec1",
       "Playgrounds within 500 m of the typical home."),
    # --- Public transport ---
    _m("rail_distance", "transit", "Nearest S-/U-Bahn or tram", "straight line", False, 2,
       "metres", "Distance to the nearest rail, S-/U-Bahn or tram stop with weekday-peak service."),
    _m("stops", "transit", "Stops within 500 m", "bus, tram and rail stops", True, 1, "dec1",
       "Public transport stops within 500 m of the typical home (OSM; a stop's platforms may "
       "count separately)."),
    _m("commute_centre", "transit", "To Alexanderplatz", "door to door, weekday peak", False, 1,
       "minutes", "Public-transport time from the area's residential centre to Alexanderplatz."),
    # --- Quiet & clean air ---
    _m("quiet", "environment", "Traffic noise", "class, 1 low – 3 high", False, 2, "dec2",
       "Berlin-relative traffic-noise burden (2022), weighted by residents."),
    _m("clean_air", "environment", "Air pollution", "class, 1 low – 3 high", False, 2, "dec2",
       "Berlin-relative NO₂/particulate burden (2023), weighted by residents."),
    _m("cool_summer", "environment", "Summer heat", "class, 1 low – 3 high", False, 1, "dec2",
       "Berlin-relative day and night heat stress (2022), weighted by residents."),
    # --- Parking ---
    _m("paid_parking", "parking", "Homes in paid-parking streets", "% of homes", False, 1, "pct",
       "Share of homes with a parking ticket machine within 150 m (a paid-parking zone)."),
    _m("parking_area", "parking", "Car parks within 300 m", "m² mapped", True, 1, "int",
       "Area of mapped car parks (incl. marked street-side parking) within 300 m of homes."),
    _m("density", "parking", "Population density", "residents per km²", False, 1, "int",
       "Registered residents per km² — more residents, more cars competing for space."),
    # --- Affordability ---
    _m("rent", "affordability", "Median asking rent", "EUR/m² net cold", False, 1, "eur_m2",
       "Median asking rent of the district, 2025 (IBB).", level="district"),
)
# fmt: on

METRICS_BY_ID = {m.id: m for m in METRICS}


def metrics_of(category_id: str) -> list[Metric]:
    return [m for m in METRICS if m.category == category_id]


OVERALL = "overall"
MAX_WEIGHT = 3
