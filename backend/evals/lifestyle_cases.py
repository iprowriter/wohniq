"""Lifestyle Match eval scenarios (pure data + predicates).

Each scenario is a set of answers plus an expectation about the ranked regions that a
sensible recommendation must meet — phrased in terms of the underlying data, not
hard-coded region names, so it stays meaningful when the data is rebuilt.

The first scenario is the Definition of Done: a student using the preset must be
offered an area near TU Berlin within a typical student budget, with reasons.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass

from lifestyle.profiles import ProfileBundle
from lifestyle.questionnaire import PRESETS_BY_ID, Answers
from lifestyle.scoring import RegionMatch

Check = Callable[[list[RegionMatch], ProfileBundle, Answers], tuple[bool, str]]


@dataclass(frozen=True)
class LifestyleScenario:
    name: str
    answers: Answers
    check: Check
    description: str


def _raw(m: RegionMatch, attribute: str) -> float:
    return m.region.measures[attribute].raw


def _score(b: ProfileBundle, m: RegionMatch, attribute: str) -> float:
    return b.score(attribute, _raw(m, attribute))


def _student_dod(results, bundle, answers):
    top3 = results[:3]
    near = [m for m in top3 if m.commute and m.commute.minutes <= 20 and m.fits_budget]
    first = results[0]
    ok = bool(near) and first.fits_budget and first.commute.minutes <= answers.max_commute_min
    detail = ", ".join(f"{m.region.name} {m.commute.minutes} min €{m.warm_rent_eur}" for m in top3)
    return ok, detail


def _family(results, bundle, answers):
    top = results[:5]
    ok = all(
        m.fits_budget and _score(bundle, m, "family") >= 0.6 and _score(bundle, m, "green") >= 0.6
        for m in top
    )
    return ok, ", ".join(f"{m.region.name}" for m in top)


def _calm_green(results, bundle, answers):
    top = results[:5]
    ok = all(_score(bundle, m, "quiet") >= 0.8 and _raw(m, "water") <= 600 for m in top)
    return ok, ", ".join(f"{m.region.name} (water {_raw(m, 'water'):.0f} m)" for m in top)


def _remote(results, bundle, answers):
    berlin = bundle.references["cafes"].berlin
    top = results[:5]
    ok = all(_raw(m, "cafes") >= berlin for m in top)
    return ok, ", ".join(f"{m.region.name} ({_raw(m, 'cafes'):.0f} cafés)" for m in top)


def _young_pro(results, bundle, answers):
    top = results[:5]
    berlin = bundle.references["cafes"].berlin
    ok = all(
        m.commute.minutes <= answers.max_commute_min and _raw(m, "cafes") >= berlin for m in top
    )
    return ok, ", ".join(f"{m.region.name} {m.commute.minutes} min" for m in top)


def _top_quartile(bundle: ProfileBundle, attribute: str) -> float:
    values = sorted(r.measures[attribute].raw for r in bundle.regions)
    return statistics.quantiles(values, n=4, method="inclusive")[2]


def _night_owl(results, bundle, answers):
    threshold = _top_quartile(bundle, "nightlife")
    top = results[:5]
    ok = all(
        _raw(m, "nightlife") >= threshold and (m.region.inner_city_share or 0) > 0.5 for m in top
    )
    detail = ", ".join(f"{m.region.name} ({_raw(m, 'nightlife'):.0f} bars)" for m in top)
    return ok, f"{detail}; top-quarter threshold {threshold:.1f}"


def _htw_student(results, bundle, answers):
    top3 = results[:3]
    ok = all(m.fits_budget and m.commute.minutes <= answers.max_commute_min for m in top3)
    return ok, ", ".join(f"{m.region.name} {m.commute.minutes} min" for m in top3)


SCENARIOS: list[LifestyleScenario] = [
    LifestyleScenario(
        "student preset → near TU Berlin, within budget (Definition of Done)",
        PRESETS_BY_ID["student"].answers,
        _student_dod,
        "Top 3 contains an area ≤ 20 min from TU Berlin where a typical 30 m² flat fits "
        "€700 warm; the #1 fits the budget and the 30-min limit.",
    ),
    LifestyleScenario(
        "student at HTW (Oberschöneweide) → areas near that campus",
        PRESETS_BY_ID["student"].answers.model_copy(update={"destination": "htw_berlin"}),
        _htw_student,
        "Same preset, different campus: top 3 within budget and within the preset's "
        "30-minute limit to HTW.",
    ),
    LifestyleScenario(
        "family preset → family-friendly and green, within budget",
        PRESETS_BY_ID["family"].answers,
        _family,
        "Top 5 fit €1,900 for 80 m² and score ≥ 0.6 on family and green space.",
    ),
    LifestyleScenario(
        "calm & green preset → quiet, water or forest close by",
        PRESETS_BY_ID["calm_green"].answers,
        _calm_green,
        "Top 5 score ≥ 0.8 on quiet and have water/forest within 600 m of the typical home.",
    ),
    LifestyleScenario(
        "remote/creative preset → café-rich neighbourhoods",
        PRESETS_BY_ID["remote_creative"].answers,
        _remote,
        "Top 5 have at least the Berlin-average number of cafés within 500 m.",
    ),
    LifestyleScenario(
        "young professional at Potsdamer Platz → quick commute, cafés",
        PRESETS_BY_ID["young_professional"].answers.model_copy(
            update={"destination": "potsdamer_platz"}
        ),
        _young_pro,
        "Top 5 within the 40-min limit and at least Berlin-average cafés.",
    ),
    LifestyleScenario(
        "night owl → inner-city nightlife hotspots",
        Answers(
            budget_eur=1200,
            size_m2=45,
            budget_strictness="flexible",
            evenings="out_often",
            weekends=("social",),
            neighbours="young",
        ),
        _night_owl,
        "Top 5 are in Berlin's top quarter of regions for bars/clubs within 1 km, and "
        "inner-city.",
    ),
]
