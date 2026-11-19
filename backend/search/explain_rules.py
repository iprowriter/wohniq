"""Pure selection logic for explanations (stdlib only, unit-testable).

Decides which ranking factors become positive "reasons" and which become honest
"caveats", purely from their scores — no LLM, no pydantic. The explanation layer
uses this for its deterministic fallback, and the same thresholds describe what the
LLM is asked to do. Operates on plain factor tuples: (name, score, weight, detail).

`relevance` is an internal retrieval signal, not a user-meaningful reason, so it's
excluded from explanations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REASON_THRESHOLD = 0.6
CAVEAT_THRESHOLD = 0.4
MAX_REASONS = 3
MAX_CAVEATS = 2

Factor = tuple[str, float, float, str]  # (name, score, weight, detail)


def _user_factors(factors: list[Factor]) -> list[Factor]:
    return [f for f in factors if f[0] != "relevance"]


def select_reasons_and_caveats(factors: list[Factor]) -> tuple[list[str], list[str]]:
    """Return (reasons, caveats) details. Reasons = strong factors (by score×weight);
    caveats = weak factors (honest trade-offs)."""
    user = _user_factors(factors)

    reasons = [
        detail
        for (_name, score, _weight, detail) in sorted(user, key=lambda f: -f[1] * f[2])
        if score >= REASON_THRESHOLD
    ][:MAX_REASONS]

    caveats = [detail for (_n, score, _w, detail) in user if score <= CAVEAT_THRESHOLD][:MAX_CAVEATS]

    # Always surface at least one reason if any user factor exists.
    if not reasons and user:
        best = max(user, key=lambda f: f[1])
        reasons = [best[3]]

    return reasons, caveats


def summary_lead(total: float) -> str:
    if total >= 0.75:
        return "A strong match"
    if total >= 0.5:
        return "A solid fit"
    return "A partial match"


# --- Contextual summary (why is this a match?) -------------------------------------------

# (name, score, weight, detail, highlight) — highlight is the short summary phrase.
HighlightFactor = tuple[str, float, float, str, str]

MAX_SUMMARY_HIGHLIGHTS = 3
MAX_TOTAL_REASONS = 4

# A summary that only grades the match ("A strong match for your search.") explains
# nothing; the explanation layer rejects these so the model re-writes them.
GENERIC_SUMMARY = re.compile(
    r"^\s*(?:this is )?(?:a|an)?\s*(?:very )?(?:strong|solid|good|great|partial|possible|decent)"
    r"\s+(?:match|fit)(?:\s+for\s+(?:your|the|this)\s+search)?\s*[.!]?\s*$",
    re.I,
)


@dataclass(frozen=True)
class MatchContext:
    """Listing facts + what the user asked for that aren't ranking factors.

    Rooms, size and furnished are hard filters, so they never appear in the factor
    breakdown — but "it has the 2 rooms you asked for" is part of *why* it matches.
    """

    kiez: str | None = None
    rooms: float | None = None
    size_m2: int | None = None
    warm_rent: int | None = None
    furnished: bool | None = None
    asked_min_rooms: float | None = None
    asked_min_size_m2: int | None = None
    asked_furnished: bool | None = None


def _fmt_rooms(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else f"{n:g}"


def requirement_reasons(ctx: MatchContext | None) -> list[tuple[str, str]]:
    """(reason, summary phrase) for each hard requirement the listing meets."""
    if ctx is None:
        return []
    out: list[tuple[str, str]] = []
    if ctx.asked_min_rooms and ctx.rooms is not None and ctx.rooms >= ctx.asked_min_rooms:
        rooms = _fmt_rooms(ctx.rooms)
        out.append(
            (f"{rooms} rooms, you asked for {_fmt_rooms(ctx.asked_min_rooms)}+", f"{rooms} rooms")
        )
    if ctx.asked_min_size_m2 and ctx.size_m2 is not None and ctx.size_m2 >= ctx.asked_min_size_m2:
        out.append(
            (f"{ctx.size_m2} m², you asked for {ctx.asked_min_size_m2}+ m²", f"{ctx.size_m2} m²")
        )
    if ctx.asked_furnished is not None and ctx.furnished == ctx.asked_furnished:
        word = "furnished" if ctx.furnished else "unfurnished"
        out.append((f"{word.capitalize()}, as you asked", word))
    return out


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _lower_first(text: str) -> str:
    first = text.split(" ", 1)[0]
    return text[0].lower() + text[1:] if first in {"No", "Not", "At", "Only"} else text


def compose_summary(
    total: float, factors: list[HighlightFactor], ctx: MatchContext | None = None
) -> str:
    """One or two sentences saying *why* the listing matches, grounded in the factors.

    "A strong match: in Lichtenberg, €471 under your €1.000 budget and a quiet Kiez with
    little nightlife."  Weak factors are admitted with ", but …".
    """
    user = [f for f in factors if f[0] != "relevance"]
    requirements = requirement_reasons(ctx)
    area = next((f for f in user if f[0] == "area"), None)
    nearby = area is not None and area[1] < REASON_THRESHOLD

    strong = [
        f[4]
        for f in sorted(user, key=lambda f: -f[1] * f[2])
        if f[1] >= REASON_THRESHOLD and f[4]
    ]
    highlights = (strong + [phrase for _, phrase in requirements])[:MAX_SUMMARY_HIGHLIGHTS]

    if not user and not requirements:
        return (
            f"{summary_lead(total).replace('strong', 'close')}: it matches the description "
            "in your search. Add a budget, area or room count for a sharper ranking."
        )

    lead = summary_lead(total)
    if nearby and area is not None:
        # "A solid fit near Mitte (Prenzlauer Berg, 1.9 km away)"
        lead = f"{lead} {area[4]}" if area[4] else f"{lead} outside the areas you asked for"
        user = [f for f in user if f[0] != "area"]  # already said; don't repeat it below
        if not user and not highlights:
            return f"{lead}: the closest flat we have to what you asked for."

    weak = [
        f[3] for f in user if f[1] <= CAVEAT_THRESHOLD and f[0] != "area"
    ]
    but = f", but {_lower_first(weak[0])}" if weak else ""

    if highlights:
        return f"{lead}: {_join(highlights)}{but}."
    if weak:
        return f"{lead}: {_lower_first(weak[0])}."
    # Only middling factors: describe the best one rather than grading alone.
    best = max(user, key=lambda f: f[1] * f[2])
    return f"{lead}: {_lower_first(best[4] or best[3])}."


def select_reasons_with_requirements(
    factors: list[Factor], ctx: MatchContext | None
) -> tuple[list[str], list[str]]:
    """Factor reasons/caveats plus the hard requirements met, up to MAX_TOTAL_REASONS."""
    reasons, caveats = select_reasons_and_caveats(factors)
    # A weak factor promoted to "reason" (the at-least-one rule) must not also be a caveat.
    reasons = [r for r in reasons if r not in caveats]
    extra = [r for r, _ in requirement_reasons(ctx) if r not in reasons]
    reasons = (reasons + extra)[: max(MAX_TOTAL_REASONS, len(reasons))]
    return reasons, caveats
