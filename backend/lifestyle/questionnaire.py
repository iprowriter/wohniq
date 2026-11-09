"""The Lifestyle Match questionnaire: questions, answers and presets (pure, no I/O).

Design:
  * Every answer is a **choice from a fixed list** (or a bounded number). There are no
    free-text fields, so answers can't carry names, addresses or anything identifying,
    and `Answers` rejects unknown fields (`extra="forbid"`).
  * Each option maps to attribute importance levels 0–5 in one table (`OPTIONS`). Weights
    are derived by taking, per attribute, the highest level any chosen option sets
    (see weights.py): monotone, order-independent, explainable ("Nightlife 3 — because
    you go out now and then").
  * A **preset** is just a pre-filled set of answers. The user sees and can change every
    answer, and the weights are always derived the same way.
  * Household type and flat size never set lifestyle weights on their own beyond what is
    stated in the option table, and no question asks about age, gender, origin, religion,
    health or income (privacy by design, ADR-0011).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


@dataclass(frozen=True)
class Option:
    id: str
    label: str
    weights: dict[str, int] = field(default_factory=dict)  # attribute -> level 0..5
    hint: str | None = None


@dataclass(frozen=True)
class Question:
    id: str
    page: str
    prompt: str
    options: tuple[Option, ...]
    multi: bool = False
    max_choices: int = 1
    help: str | None = None


# --- Pages (the multi-step UI follows this order) -------------------------------------

PAGES: tuple[tuple[str, str, str], ...] = (
    ("move", "Your move", "Who's moving, how much space, and what you can spend."),
    ("days", "Your days", "Where you go most and how you get around."),
    ("free_time", "Evenings & weekends", "How you like to spend your free time."),
    ("neighbourhood", "Your neighbourhood", "What else makes a place feel right."),
)

# --- Questions with options -------------------------------------------------------------

QUESTIONS: tuple[Question, ...] = (
    Question(
        "household",
        "move",
        "Who's moving?",
        (
            Option("solo", "Just me"),
            Option("couple", "Me and my partner"),
            Option("family", "A family with kids", {"family": 5, "everyday": 4}),
            Option("flatshare", "Friends / a flatshare"),
        ),
    ),
    Question(
        "budget_strictness",
        "move",
        "How firm is your budget?",
        (
            Option("strict", "Firm — every euro counts", {"affordability": 5}),
            Option("balanced", "Some wiggle room", {"affordability": 3}),
            Option("flexible", "Flexible for the right place", {"affordability": 1}),
        ),
    ),
    Question(
        "frequency",
        "days",
        "How often do you go there?",
        (
            Option("daily", "Every day", {"commute": 5}),
            Option("most_days", "Most days", {"commute": 4}),
            Option("few_times", "A few times a week", {"commute": 3}),
            Option("rarely", "Now and then", {"commute": 1}),
        ),
        help="Only counts if you pick a destination.",
    ),
    Question(
        "work_style",
        "days",
        "How do you work or study?",
        (
            Option("on_site", "On campus / at the office"),
            Option("hybrid", "Hybrid — some days from home", {"cafes": 3}),
            Option(
                "remote_creative",
                "Remote or creative — the neighbourhood is my office",
                {"cafes": 5, "culture": 4, "young_crowd": 3},
            ),
        ),
    ),
    Question(
        "getting_around",
        "days",
        "How do you mostly get around?",
        (
            Option("public_transport", "U-Bahn, S-Bahn & tram", {"transit": 4}),
            Option("mix", "A bit of everything", {"transit": 3}),
            Option("bike", "By bike", {"transit": 2}),
            Option("car", "By car"),
        ),
    ),
    Question(
        "evenings",
        "free_time",
        "What do your evenings look like?",
        (
            Option("out_often", "Out most nights — bars, gigs, clubs", {"nightlife": 5}),
            Option("sometimes", "Out now and then, cosy at home otherwise", {"nightlife": 3}),
            Option("home", "Mostly at home — a quiet street matters", {"quiet": 4}),
            Option("calm", "Peace and quiet is essential", {"quiet": 5}),
            Option("no_preference", "No strong preference"),
        ),
    ),
    Question(
        "weekends",
        "free_time",
        "Your ideal weekend? (pick up to two)",
        (
            Option("nature", "Lakes, forests and long walks", {"green": 5, "water": 4}),
            Option(
                "park_cafe", "A park and a good café around the corner", {"green": 3, "cafes": 3}
            ),
            Option("social", "Friends, bars and cafés", {"cafes": 3, "nightlife": 3}),
            Option("brunch", "Brunch spots and exploring the Kiez", {"cafes": 4}),
            Option("culture", "Museums, galleries, a show", {"culture": 3}),
            Option("active", "Sport and staying active", {"sport": 4}),
            Option("family_time", "Playgrounds and family outings", {"green": 5, "family": 5}),
        ),
        multi=True,
        max_choices=2,
    ),
    Question(
        "neighbours",
        "neighbourhood",
        "Who would you like around you?",
        (
            Option("young", "A young crowd — students and young professionals", {"young_crowd": 4}),
            Option("families", "Lots of families", {"family": 4}),
            Option("mix", "A mix — doesn't matter"),
        ),
    ),
    Question(
        "safety",
        "neighbourhood",
        "How much should reported neighbourhood crime count?",
        (
            Option("none", "Not a factor for me"),
            Option("little", "A little", {"safety": 1}),
            Option("some", "Somewhat", {"safety": 3}),
            Option("lot", "A lot", {"safety": 4}),
            Option("top", "It's a top priority", {"safety": 5}),
        ),
        help="Based on police statistics per 100,000 residents. Busy central areas read "
        "higher because visitors count too.",
    ),
    Question(
        "extras",
        "neighbourhood",
        "Anything else? (optional)",
        (
            Option("clean_air", "Clean air", {"clean_air": 4}),
            Option("cool_summer", "Cooler summer nights", {"cool_summer": 4}),
        ),
        multi=True,
        max_choices=2,
    ),
)

QUESTIONS_BY_ID: dict[str, Question] = {q.id: q for q in QUESTIONS}


# --- Answers ----------------------------------------------------------------------------

Household = Literal["solo", "couple", "family", "flatshare"]
Strictness = Literal["strict", "balanced", "flexible"]
Frequency = Literal["daily", "most_days", "few_times", "rarely"]
WorkStyle = Literal["on_site", "hybrid", "remote_creative"]
GettingAround = Literal["public_transport", "mix", "bike", "car"]
Evenings = Literal["out_often", "sometimes", "home", "calm", "no_preference"]
Weekend = Literal["nature", "park_cafe", "social", "brunch", "culture", "active", "family_time"]
Neighbours = Literal["young", "families", "mix"]
Safety = Literal["none", "little", "some", "lot", "top"]
Extra = Literal["clean_air", "cool_summer"]


class Answers(BaseModel):
    """Everything the user tells us. Bounded choices only; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    household: Household | None = None
    budget_eur: int = Field(ge=200, le=10_000)  # warm rent per month
    size_m2: int = Field(ge=10, le=250)
    rooms: float = Field(default=1, ge=1, le=8)
    budget_strictness: Strictness | None = None
    destination: str | None = Field(default=None, max_length=40)  # a Destination.id
    frequency: Frequency | None = None
    max_commute_min: int = Field(default=45, ge=10, le=120)
    work_style: WorkStyle | None = None
    getting_around: GettingAround | None = None
    evenings: Evenings | None = None
    weekends: tuple[Weekend, ...] = ()
    neighbours: Neighbours | None = None
    safety: Safety | None = None
    extras: tuple[Extra, ...] = ()

    @field_validator("weekends", "extras")
    @classmethod
    def _unique_and_bounded(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate choice")
        if len(value) > QUESTIONS_BY_ID[info.field_name].max_choices:
            raise ValueError(f"pick at most {QUESTIONS_BY_ID[info.field_name].max_choices}")
        return value

    def chosen(self) -> list[tuple[Question, Option]]:
        """(question, option) for every answered option question, in catalogue order."""
        out: list[tuple[Question, Option]] = []
        for q in QUESTIONS:
            value = getattr(self, q.id)
            picked = value if q.multi else ((value,) if value is not None else ())
            for opt in q.options:
                if opt.id in picked:
                    out.append((q, opt))
        return out


# --- Presets ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    blurb: str
    answers: Answers


PRESETS: tuple[Preset, ...] = (
    Preset(
        "student",
        "Student",
        "Close to campus, easy on the wallet, a young crowd around you.",
        Answers(
            household="solo",
            budget_eur=700,
            size_m2=30,
            rooms=1,
            budget_strictness="strict",
            destination="tu_berlin",
            frequency="daily",
            max_commute_min=30,
            work_style="on_site",
            getting_around="public_transport",
            evenings="sometimes",
            weekends=("social",),
            neighbours="young",
            safety="none",
        ),
    ),
    Preset(
        "young_professional",
        "Young professional",
        "A quick ride to work, great cafés and something on in the evening.",
        Answers(
            household="solo",
            budget_eur=1400,
            size_m2=55,
            rooms=2,
            budget_strictness="flexible",
            frequency="most_days",
            max_commute_min=40,
            work_style="on_site",
            getting_around="public_transport",
            evenings="sometimes",
            weekends=("brunch", "culture"),
            neighbours="mix",
            safety="some",
        ),
    ),
    Preset(
        "family",
        "Family",
        "Space, parks and playgrounds, daily errands close by, a calm and safe street.",
        Answers(
            household="family",
            budget_eur=1900,
            size_m2=80,
            rooms=3,
            budget_strictness="flexible",
            frequency="few_times",
            evenings="home",
            weekends=("family_time",),
            neighbours="families",
            safety="top",
        ),
    ),
    Preset(
        "remote_creative",
        "Remote / creative",
        "Your Kiez is your office: cafés, culture and creative energy.",
        Answers(
            household="solo",
            budget_eur=1200,
            size_m2=55,
            rooms=2,
            budget_strictness="flexible",
            work_style="remote_creative",
            evenings="no_preference",
            weekends=("park_cafe",),
            neighbours="mix",
            safety="none",
        ),
    ),
    Preset(
        "calm_green",
        "Calm & green",
        "Quiet streets, parks, water and forest within reach.",
        Answers(
            household="couple",
            budget_eur=1300,
            size_m2=55,
            rooms=2,
            budget_strictness="flexible",
            evenings="calm",
            weekends=("nature",),
            neighbours="mix",
            safety="lot",
        ),
    ),
)

PRESETS_BY_ID: dict[str, Preset] = {p.id: p for p in PRESETS}
