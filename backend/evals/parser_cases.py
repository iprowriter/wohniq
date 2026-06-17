"""20 canonical parser eval cases (pure data).

Each case has a query and an `expected` partial criteria dict — only the fields we
can assert unambiguously. Cases deliberately include hard ones: vague vibe queries,
under-specified requests (where budget/size must stay null — no hallucinating), and
amenity/transport/quiet phrasing variety.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalCase:
    query: str
    expected: dict


CASES: list[EvalCase] = [
    EvalCase(
        "I work near Alexanderplatz, budget €1,500, want a quiet neighborhood, "
        "good public transport, cafes nearby",
        {
            "max_warm_rent": 1500,
            "work_location": "Alexanderplatz",
            "quiet_priority": True,
            "transport_priority": True,
            "desired_amenities": ["cafes"],
        },
    ),
    EvalCase(
        "2-room flat around 60m² in Kreuzberg, furnished",
        {"min_rooms": 2, "min_size_m2": 60, "furnished": True},
    ),
    EvalCase(
        "Somewhere I can bike to work, not too loud, max 1200 euros",
        {"max_warm_rent": 1200, "quiet_priority": True, "min_rooms": None},
    ),
    EvalCase(
        "Looking for a lively area with bars and clubs, 1 bedroom",
        {"min_rooms": 1, "desired_amenities": ["nightlife"]},
    ),
    EvalCase(
        "3 rooms for a family, near a park, quiet street",
        {"min_rooms": 3, "quiet_priority": True, "desired_amenities": ["parks"]},
    ),
    EvalCase(
        "1-room near Friedrichshain, good transport links",
        {"min_rooms": 1, "transport_priority": True},
    ),
    EvalCase(
        "I need a furnished apartment with a gym nearby, 2.5 rooms",
        {"min_rooms": 2.5, "furnished": True, "desired_amenities": ["gym"]},
    ),
    EvalCase(
        "unfurnished 4-room, around 100 square meters",
        {"min_rooms": 4, "min_size_m2": 100, "furnished": False},
    ),
    EvalCase(
        "quiet residential area, close to a supermarket",
        {"quiet_priority": True, "desired_amenities": ["supermarket"]},
    ),
    EvalCase(
        "cheap place under 1000, doesn't matter where",
        {"max_warm_rent": 1000},
    ),
    EvalCase(
        "near my office at Potsdamer Platz, 2 rooms, cafes and parks",
        {
            "work_location": "Potsdamer Platz",
            "min_rooms": 2,
            "desired_amenities": ["cafes", "parks"],
        },
    ),
    EvalCase(
        "I want nightlife, bars, and good transport, budget 1800",
        {"max_warm_rent": 1800, "transport_priority": True, "desired_amenities": ["nightlife"]},
    ),
    EvalCase(
        "peaceful 1.5-room flat, furnished, max €1,100",
        {"min_rooms": 1.5, "furnished": True, "quiet_priority": True, "max_warm_rent": 1100},
    ),
    EvalCase(
        "70m2, 3 rooms, near U-Bahn",
        {"min_size_m2": 70, "min_rooms": 3, "transport_priority": True},
    ),
    EvalCase(
        "just a place with lots of cafes and a gym nearby",
        {"desired_amenities": ["cafes", "gym"]},
    ),
    EvalCase(
        "work at Alexanderplatz, prefer quiet, no preference on size or budget",
        {
            "work_location": "Alexanderplatz",
            "quiet_priority": True,
            "max_warm_rent": None,
            "min_size_m2": None,
        },
    ),
    EvalCase(
        "2 bedroom, supermarket and park within walking distance",
        {"min_rooms": 2, "desired_amenities": ["supermarket", "parks"]},
    ),
    EvalCase(
        "furnished studio in a vibrant nightlife district near the S-Bahn, €1,400",
        {
            "furnished": True,
            "transport_priority": True,
            "desired_amenities": ["nightlife"],
            "max_warm_rent": 1400,
        },
    ),
    EvalCase(
        "somewhere calm to live, 2 rooms",
        {"min_rooms": 2, "quiet_priority": True},
    ),
    EvalCase(
        "good commute to Mitte, 3 rooms, under 2000",
        {
            "work_location": "Mitte",
            "min_rooms": 3,
            "max_warm_rent": 2000,
            "transport_priority": True,
        },
    ),
]
