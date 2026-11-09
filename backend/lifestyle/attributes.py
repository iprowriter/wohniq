"""Catalogue of Lifestyle Match attributes — what a neighbourhood can be scored on.

Two kinds:
  * "area"     — a property of the region, measured from public data and stored in the
                 profile bundle (e.g. safety from the police crime atlas).
  * "personal" — computed per request from the user's own inputs (budget, commute
                 destination) against the region; never stored.

Whether an attribute is *available* is not declared here — it is derived from the
bundle (an attribute is available iff the bundle carries a reference range for it).
So the catalogue can list attributes whose data hasn't arrived yet (`requires` says
what's missing) without the code and the data drifting apart.

Why these attributes: they are the factors people weigh when choosing where to live —
cost and commute first, then neighbourhood qualities (safety, quiet, green space,
amenities, family infrastructure, social scene). See ADR-0010 for the sourcing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["area", "personal"]


@dataclass(frozen=True)
class Attribute:
    id: str
    label: str
    description: str  # user-facing: what the score measures, in one sentence
    kind: Kind
    # Direction of the *raw* measure: True if a larger raw value is better for someone
    # who cares about this attribute (share of families), False if smaller is better
    # (offences per 100k residents). Scores are always "higher = better fit".
    higher_is_better: bool = True
    requires: str | None = None  # data still needed, for attributes not yet in the bundle


ATTRIBUTES: tuple[Attribute, ...] = (
    # --- Personal: computed per request, never stored -----------------------------
    Attribute(
        "affordability",
        "Affordability",
        "How typical rents for your flat size compare with your budget.",
        "personal",
    ),
    Attribute(
        "commute",
        "Commute",
        "Public-transport time from the area to the place you go most.",
        "personal",
    ),
    # --- Area: measured from public data ------------------------------------------
    Attribute(
        "safety",
        "Safety",
        "Reported neighbourhood offences per 100,000 residents (lower is safer).",
        "area",
        higher_is_better=False,
    ),
    Attribute(
        "family",
        "Family-friendly",
        "Share of residents under 18 — how many families already live here.",
        "area",
    ),
    Attribute(
        "young_crowd",
        "Young crowd",
        "Share of residents aged 18–27 — students and young professionals.",
        "area",
    ),
    Attribute(
        "quiet",
        "Quiet",
        "Low exposure to traffic noise (road, rail, tram, air) where people live.",
        "area",
        higher_is_better=False,  # raw = mean burden class (1 low – 3 high)
    ),
    Attribute(
        "green",
        "Green space",
        "Public parks within walking distance, relative to how many people share them.",
        "area",
        higher_is_better=False,  # raw = mean burden class (1 low – 3 high)
    ),
    Attribute(
        "clean_air",
        "Clean air",
        "Low air pollution (NO₂ and fine particles).",
        "area",
        higher_is_better=False,  # raw = mean burden class (1 low – 3 high)
    ),
    Attribute(
        "cool_summer",
        "Cooler summers",
        "Less heat stress on hot days and warm nights.",
        "area",
        higher_is_better=False,  # raw = mean burden class (1 low – 3 high)
    ),
    Attribute(
        "nightlife",
        "Nightlife",
        "Bars, pubs, clubs and beer gardens within about a 12-minute walk.",
        "area",
    ),
    Attribute(
        "cafes",
        "Cafés & food",
        "Cafés, restaurants and bakeries within about a 6-minute walk.",
        "area",
    ),
    Attribute(
        "culture",
        "Culture",
        "Museums, theatres, cinemas, arts centres and libraries nearby.",
        "area",
    ),
    Attribute(
        "everyday",
        "Everyday errands",
        "Supermarkets, pharmacies and doctors within about a 6-minute walk.",
        "area",
    ),
    Attribute(
        "sport",
        "Sport & fitness",
        "Gyms, pools and sports centres within about a 12-minute walk.",
        "area",
    ),
    Attribute(
        "water",
        "Water & nature",
        "Lakes, rivers, canals and forest within reach.",
        "area",
        higher_is_better=False,  # raw = distance in metres
    ),
    Attribute(
        "transit",
        "Transit access",
        "A short walk to the S-Bahn, U-Bahn, regional train or tram.",
        "area",
        higher_is_better=False,  # raw = distance in metres
    ),
)

ATTRIBUTES_BY_ID: dict[str, Attribute] = {a.id: a for a in ATTRIBUTES}


def get_attribute(attribute_id: str) -> Attribute:
    try:
        return ATTRIBUTES_BY_ID[attribute_id]
    except KeyError:
        raise KeyError(f"Unknown lifestyle attribute: {attribute_id!r}") from None
