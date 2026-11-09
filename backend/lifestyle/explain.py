"""Explanations for Lifestyle Match results — deterministic templates, no LLM (ADR-0011).

Every sentence is generated from a scored `Factor` (the same numbers that produced the
rank) and names its source, so an explanation can never claim something the data
doesn't say. Three parts per region:

  * headline  — one line: what it's strong on;
  * reasons   — up to three strengths, each with the figure behind it;
  * caveats   — honest trade-offs: over budget, beyond the commute limit, weak spots on
                things the user cares about;
  * notes     — caveats about the data itself (district rents vary; crime statistics in
                busy central areas), shown with "the data behind this".
"""

from __future__ import annotations

from dataclasses import dataclass

from lifestyle.profiles import ProfileBundle
from lifestyle.questionnaire import Answers
from lifestyle.scoring import Factor, RegionMatch

STRENGTH_MIN_SCORE = 0.6
WEAK_MAX_SCORE = 0.35
WEAK_MIN_WEIGHT = 3
MAX_REASONS = 3

# Class-based indicators (Umweltgerechtigkeitsatlas): how to name the best/worst class.
_CLASS_WORDS = {
    "quiet": ("lowest traffic-noise class", "highest"),
    "clean_air": ("lowest air-pollution class", "highest"),
    "cool_summer": ("lowest heat-stress class", "highest"),
    "green": ("best green-space supply class", "poorest"),
}
_DISTANCE_NOUN = {
    "water": "Nearest lake, river, canal or forest",
    "transit": "Nearest S-/U-Bahn, regional-train or tram stop",
}


@dataclass(frozen=True)
class Evidence:
    attribute: str
    label: str
    text: str  # one sentence with the figure
    source_id: str
    score: float
    weight: int


@dataclass(frozen=True)
class Explanation:
    headline: str
    reasons: list[Evidence]
    caveats: list[str]
    evidence: list[Evidence]  # every scored factor, for the "data behind this" view
    notes: list[str]  # caveats about the data, not trade-offs of the area


def _distance(metres: float) -> str:
    if metres < 1000:
        return f"{round(metres, -1):.0f} m"
    return f"{metres / 1000:.1f} km"


def _euros(value: float) -> str:
    return f"€{value:,.0f}"


def factor_text(factor: Factor, match: RegionMatch, bundle: ProfileBundle, answers: Answers) -> str:
    """One factual sentence for a factor, built only from its numbers."""
    a = factor.attribute
    region = match.region
    if a == "affordability":
        running = (
            bundle.city["operating_costs_cold"].value + bundle.city["operating_costs_warm"].value
        )
        rent = region.rent.raw if region.rent else bundle.city["asking_rent_median"].value
        diff = answers.budget_eur - match.warm_rent_eur
        where = "under" if diff >= 0 else "over"
        return (
            f"A {answers.size_m2} m² flat typically costs ≈ {_euros(match.warm_rent_eur)} warm "
            f"here ({region.district} median asking rent €{rent:.2f}/m² + €{running:.2f}/m² "
            f"running costs) — {_euros(abs(diff))} {where} your {_euros(answers.budget_eur)} "
            "budget."
        )
    if a == "commute" and match.commute is not None:
        dest = bundle.destination(answers.destination or "")
        name = dest.short if dest else "your destination"
        c = match.commute
        text = f"≈ {c.minutes} min to {name} by public transport"
        if c.source == "network" and c.changes is not None:
            text += ", direct" if c.changes == 0 else f", {c.changes} change{'s' * (c.changes > 1)}"
        if c.source == "distance":
            text += " (estimated from distance)"
        return text + " in the weekday morning peak."
    if a == "safety":
        berlin = factor.berlin or 0
        diff = (factor.raw - berlin) / berlin * 100 if berlin else 0
        side = "below" if diff < 0 else "above"
        return (
            f"{factor.raw:,.0f} neighbourhood offences per 100,000 residents a year — "
            f"{abs(diff):.0f}% {side} the Berlin average ({berlin:,.0f})."
        )
    if a == "family":
        return f"{factor.raw:.1f}% of residents are under 18 (Berlin: {factor.berlin:.1f}%)."
    if a == "young_crowd":
        return f"{factor.raw:.1f}% of residents are aged 18–27 (Berlin: {factor.berlin:.1f}%)."
    if a in _CLASS_WORDS:
        shares = region.measures[a].shares or {}
        best_word, worst_word = _CLASS_WORDS[a]
        return (
            f"{shares.get('best', 0):.0f}% of residents live in Berlin's {best_word}, "
            f"{shares.get('worst', 0):.0f}% in the {worst_word}."
        )
    if a in _DISTANCE_NOUN:
        return (
            f"{_DISTANCE_NOUN[a]} ≈ {_distance(factor.raw)} from the typical home "
            f"(Berlin: {_distance(factor.berlin or 0)})."
        )
    # Amenity counts: the unit already says what and within which radius.
    return (
        f"≈ {factor.raw:.0f} {factor.unit} of the typical home "
        f"(Berlin: {factor.berlin or 0:.0f})."
    )


def _join(labels: list[str]) -> str:
    labels = [label.lower() for label in labels]
    if len(labels) <= 1:
        return "".join(labels)
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def explain_match(match: RegionMatch, bundle: ProfileBundle, answers: Answers) -> Explanation:
    evidence = [
        Evidence(
            f.attribute,
            f.label,
            factor_text(f, match, bundle, answers),
            f.source_id,
            f.score,
            f.weight,
        )
        for f in match.factors  # already sorted by contribution
    ]
    reasons = [e for e in evidence if e.score >= STRENGTH_MIN_SCORE][:MAX_REASONS]

    caveats: list[str] = []
    if not match.fits_budget:
        over = match.warm_rent_eur - answers.budget_eur
        caveats.append(
            f"Typical flats here (≈ {_euros(match.warm_rent_eur)} warm for "
            f"{answers.size_m2} m²) are {_euros(over)} over your budget, so it's ranked lower."
        )
    if match.within_commute is False and match.commute is not None:
        caveats.append(
            f"≈ {match.commute.minutes} min to your destination is more than your "
            f"{answers.max_commute_min}-minute limit, so it's ranked lower."
        )
    for e in evidence:
        if e.weight >= WEAK_MIN_WEIGHT and e.score < WEAK_MAX_SCORE:
            caveats.append(f"Weaker on {e.label.lower()}: {e.text}")
    notes: list[str] = []
    weighted = {f.attribute for f in match.factors}
    region = match.region
    if "affordability" in weighted and region.rent_range:
        low, high = region.rent_range
        notes.append(
            f"Rent is the {region.district} district median; 80% of offers there ask "
            f"€{low:.2f}–{high:.2f}/m², so individual flats vary a lot."
        )
    if "safety" in weighted and (region.inner_city_share or 0) >= 0.5:
        safety = region.measures.get("safety")
        ref = bundle.references.get("safety")
        if safety and ref and safety.raw > ref.berlin:
            notes.append(
                "Central, busy areas read higher on crime statistics because visitors' "
                "incidents count against residents; the police note this can also reflect "
                "how lively a place is."
            )

    if reasons:
        headline = f"Strong on {_join([r.label for r in reasons])}."
    else:
        headline = "A partial fit — see the trade-offs below."
    return Explanation(headline, reasons, caveats, evidence, notes)
