"""SearchCriteria — the structured output of the query parser (F1).

Shared contract: the parser produces it, retrieval filters on it, ranking scores
against it, and explanations reference it. Optional fields default to null/false so
an under-specified query never forces a guess (SPEC F1 AC2).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from search.areas import canonical_areas
from search.parse_rules import CANONICAL_AMENITIES


class SearchCriteria(BaseModel):
    max_warm_rent: int | None = None  # EUR/month, warm (all-in)
    min_rooms: float | None = None
    min_size_m2: int | None = None
    work_location: str | None = None  # free-text place name, e.g. "Alexanderplatz"
    transport_priority: bool = False
    quiet_priority: bool = False
    desired_amenities: list[str] = Field(default_factory=list)
    furnished: bool | None = None
    # Berlin areas the user wants to LIVE in (canonical names from search/areas.py,
    # e.g. ["Mitte", "Prenzlauer Berg"]). Empty = anywhere. These are a hard filter.
    areas: list[str] = Field(default_factory=list)
    # Areas the user explicitly doesn't want ("anything but Neukölln").
    excluded_areas: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("areas", "excluded_areas")
    @classmethod
    def _only_known_areas(cls, value: list[str]) -> list[str]:
        """Map names/nicknames ("P'berg", "Xberg") to canonical areas; drop unknown ones."""
        return canonical_areas(value)

    @field_validator("desired_amenities")
    @classmethod
    def _only_canonical(cls, value: list[str]) -> list[str]:
        """Keep only canonical amenity tags, de-duplicated, regardless of LLM output."""
        result: list[str] = []
        for item in value:
            tag = item.strip().lower()
            if tag in CANONICAL_AMENITIES and tag not in result:
                result.append(tag)
        return result
