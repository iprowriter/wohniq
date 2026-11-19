"""Why did a search come back empty (or thin)? Pure, stdlib-only diagnosis.

The search router asks two questions when results are missing:

1. Is the budget the blocker? We look at the listings that match every *other*
   requirement (areas, rooms, size, furnished) and compare their warm rents with the
   budget. If none fit, we recommend the minimum budget that would show at least one
   flat — and a slightly higher one that would give a few options to choose from.
   Listings with a *high* scam-risk band are ignored here: a suspiciously cheap
   price-bait listing must never set the recommended budget.

2. If the user named areas and nothing matched in them, what's nearby? (The router
   fetches nearby listings; this module only words the notice.)

Every message states concrete numbers, and nothing here touches the network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from search.areas import describe_areas

BUDGET_STEP_EUR = 10  # recommended minimum is rounded up to this
COMFORT_STEP_EUR = 50  # the "a few options" budget is rounded up to this
COMFORT_OPTIONS = 3

BUDGET_TOO_LOW = "budget_too_low"
BUDGET_TOO_LOW_IN_SOME_AREAS = "budget_too_low_in_some_areas"
NEARBY_RESULTS = "nearby_results"
NO_LISTINGS_IN_AREA = "no_listings_in_area"
NO_RESULTS = "no_results"


@dataclass(frozen=True)
class Notice:
    kind: str
    title: str
    message: str
    suggested_budget: int | None = None  # recommended minimum warm rent
    comfortable_budget: int | None = None  # shows ~COMFORT_OPTIONS flats
    options_at_suggested: int | None = None
    options_at_comfortable: int | None = None


@dataclass(frozen=True)
class BudgetAdvice:
    budget: int
    cheapest: int
    suggested_budget: int
    options_at_suggested: int
    comfortable_budget: int | None
    options_at_comfortable: int | None


def _round_up(value: int, step: int) -> int:
    return int(math.ceil(value / step) * step)


def _euro(value: int) -> str:
    return f"€{value:,}".replace(",", ".")  # €1.010, as the UI formats prices


def budget_advice(budget: int | None, rents: list[int]) -> BudgetAdvice | None:
    """Advice if `budget` is below every rent in `rents`; None if the budget isn't the issue.

    `rents` are the warm rents of listings matching all other requirements (already
    without high-risk listings).
    """
    if not budget or not rents or min(rents) <= budget:
        return None
    ordered = sorted(rents)
    suggested = _round_up(ordered[0], BUDGET_STEP_EUR)
    at_suggested = sum(1 for r in ordered if r <= suggested)
    comfortable: int | None = None
    at_comfortable: int | None = None
    if len(ordered) > at_suggested and at_suggested < COMFORT_OPTIONS:
        target = ordered[min(COMFORT_OPTIONS, len(ordered)) - 1]
        comfortable = _round_up(target, COMFORT_STEP_EUR)
        at_comfortable = sum(1 for r in ordered if r <= comfortable)
    return BudgetAdvice(
        budget=budget,
        cheapest=ordered[0],
        suggested_budget=suggested,
        options_at_suggested=at_suggested,
        comfortable_budget=comfortable,
        options_at_comfortable=at_comfortable,
    )


def _flats(n: int) -> str:
    return "1 flat" if n == 1 else f"{n} flats"


def requirements_phrase(
    min_rooms: float | None, min_size_m2: int | None, furnished: bool | None
) -> str:
    """' with 2+ rooms and 60+ m², furnished' — or '' if nothing was required."""
    parts = []
    if min_rooms:
        parts.append(f"{min_rooms:g}+ rooms")
    if min_size_m2:
        parts.append(f"{min_size_m2}+ m²")
    phrase = f" with {' and '.join(parts)}" if parts else ""
    if furnished is not None:
        word = "furnished" if furnished else "unfurnished"
        phrase += f", {word}" if phrase else f" that are {word}"
    return phrase


def budget_notice(advice: BudgetAdvice, areas: list[str], requirements: str = "") -> Notice:
    scope = f"in {describe_areas(areas)}" if areas else "in Berlin"
    message = (
        f"No flats {scope}{requirements} fit a budget of {_euro(advice.budget)} warm. "
        f"The cheapest one is {_euro(advice.cheapest)} warm, so raise your budget to at "
        f"least {_euro(advice.suggested_budget)} to see "
        f"{'it' if advice.options_at_suggested == 1 else _flats(advice.options_at_suggested)}"
    )
    if advice.comfortable_budget and advice.options_at_comfortable:
        message += (
            f", or to {_euro(advice.comfortable_budget)} for "
            f"{_flats(advice.options_at_comfortable)} to choose from"
        )
    return Notice(
        kind=BUDGET_TOO_LOW,
        title=f"Your budget is too low for {describe_areas(areas) or 'Berlin'}",
        message=message + ".",
        suggested_budget=advice.suggested_budget,
        comfortable_budget=advice.comfortable_budget,
        options_at_suggested=advice.options_at_suggested,
        options_at_comfortable=advice.options_at_comfortable,
    )


def partial_budget_notice(budget: int, blocked: dict[str, int]) -> Notice | None:
    """Some requested areas have flats, but none within budget: say which, and the cheapest."""
    if not blocked:
        return None
    parts = [f"{area} (from {_euro(rent)} warm)" for area, rent in blocked.items()]
    names = describe_areas(list(blocked), conj="and")
    return Notice(
        kind=BUDGET_TOO_LOW_IN_SOME_AREAS,
        title=f"Nothing in {names} within {_euro(budget)}",
        message=(
            f"Your budget of {_euro(budget)} warm is too low for "
            f"{describe_areas(parts, conj='and')}, so the results only come from your "
            "other areas."
        ),
        suggested_budget=_round_up(min(blocked.values()), BUDGET_STEP_EUR),
    )


def no_listings_notice(areas: list[str], requirements: str = "") -> Notice:
    return Notice(
        kind=NO_LISTINGS_IN_AREA,
        title=f"No listings in {describe_areas(areas)} right now",
        message=(
            f"We don't have any flats in {describe_areas(areas)}{requirements} at the moment, "
            "at any price."
        ),
    )


def nearby_notice(
    areas: list[str],
    count: int,
    max_km: float,
    *,
    none_in_area: bool = False,
    requirements: str = "",
    closest: tuple[str, float] | None = None,
) -> Notice:
    """Nothing inside the requested areas: we show (or couldn't find) nearby flats.

    `none_in_area` — there are no listings there at all (vs. none matching the other
    requirements). `closest` — (Kiez, km) of the nearest flat beyond `max_km`, offered
    when nothing is close enough to count as nearby.
    """
    where = describe_areas(areas)
    if count:
        if none_in_area:
            title = f"No listings in {where} right now — showing flats nearby"
            lead = f"We don't have flats in {where}{requirements} at the moment"
        else:
            title = f"Showing flats near {where}"
            lead = f"Nothing inside {where} matched all of your requirements"
        return Notice(
            kind=NEARBY_RESULTS,
            title=title,
            message=(
                f"{lead}, so these are the closest matching flats (within {max_km:g} km). "
                "Each card shows how far it is from the area you asked for."
            ),
        )
    message = (
        f"We don't have flats{requirements} in {where} or within {max_km:g} km of it right now."
    )
    if closest is not None:
        kiez, km = closest
        message += f" The closest matching flats are in {kiez}, {km:.0f} km away."
    else:
        message += " Try another area or fewer requirements."
    return Notice(kind=NO_RESULTS, title=f"Nothing in or near {where}", message=message)


def no_results_notice(requirements: str) -> Notice:
    return Notice(
        kind=NO_RESULTS,
        title="No flats match all of your requirements",
        message=(
            f"We have no flats{requirements} right now. "
            "Try a smaller room count or size, or drop the furnished requirement."
            if requirements
            else "No flats match your search right now. Try describing it differently."
        ),
    )
