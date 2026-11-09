"""A playful, respectful "lifestyle persona" from the user's weights (deterministic).

Rules are checked in order and the first match wins. They look only at what the user
told us they care about (weights and destination type) — never at household, budget
size or anything that could stand in for age, gender, origin or income — and the copy
describes preferences, not the person. The UI always asks "Did we get this right?" and
lets the user change their answers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lifestyle.attributes import ATTRIBUTES_BY_ID
from lifestyle.profiles import ProfileBundle
from lifestyle.questionnaire import Answers

DISCLAIMER = "Based only on your answers — change any of them and this updates."


@dataclass(frozen=True)
class Persona:
    id: str
    title: str
    emoji: str
    tagline: str
    priorities: list[str]  # labels of the top-weighted attributes
    summary: str  # tagline + priorities in one sentence
    disclaimer: str = DISCLAIMER


Rule = Callable[[dict[str, int], str | None], bool]


def _w(weights: dict[str, int], attribute: str) -> int:
    return weights.get(attribute, 0)


# (id, title, emoji, tagline, rule(weights, destination_kind))
_RULES: list[tuple[str, str, str, str, Rule]] = [
    (
        "campus_explorer",
        "The Campus Explorer",
        "🎓",
        "Lectures by day, the Kiez by night — close to campus and easy on the wallet.",
        lambda w, kind: kind == "university"
        and _w(w, "commute") >= 4
        and (_w(w, "young_crowd") >= 3 or _w(w, "affordability") >= 4),
    ),
    (
        "nest_builder",
        "The Nest Builder",
        "🏡",
        "Room to grow: playgrounds, parks and everyday errands around the corner.",
        lambda w, kind: _w(w, "family") >= 4,
    ),
    (
        "green_retreater",
        "The Green Retreater",
        "🌳",
        "City access, country calm: quiet streets with water and trees nearby.",
        lambda w, kind: _w(w, "quiet") >= 4 and (_w(w, "green") >= 4 or _w(w, "water") >= 4),
    ),
    (
        "night_owl",
        "The Night Owl",
        "🌙",
        "The city comes alive after dark — and you want to be in the middle of it.",
        lambda w, kind: _w(w, "nightlife") >= 4,
    ),
    (
        "urban_go_getter",
        "The Urban Go-Getter",
        "🚇",
        "Fast connections, good coffee and something on after work.",
        lambda w, kind: _w(w, "commute") >= 4 and _w(w, "transit") >= 4,
    ),
    (
        "kiez_creative",
        "The Kiez Creative",
        "🎨",
        "Your neighbourhood is your office: cafés, culture and creative energy.",
        lambda w, kind: _w(w, "cafes") >= 4 and _w(w, "culture") >= 3,
    ),
    (
        "culture_collector",
        "The Culture Collector",
        "🎭",
        "Museums, stages and screens within easy reach.",
        lambda w, kind: _w(w, "culture") >= 4,
    ),
    (
        "active_urbanite",
        "The Active Urbanite",
        "🏃",
        "Gyms, pools and pitches close by — the city is your training ground.",
        lambda w, kind: _w(w, "sport") >= 4,
    ),
    (
        "smart_commuter",
        "The Smart Commuter",
        "⏱️",
        "Less time on the train, more time for life.",
        lambda w, kind: _w(w, "commute") >= 4,
    ),
]
_FALLBACK = (
    "berlin_balancer",
    "The Berlin Balancer",
    "⚖️",
    "A bit of everything — you want a place that gets the balance right.",
)


def top_priorities(weights: dict[str, int], n: int = 3) -> list[str]:
    """Labels of the n highest weights (ties broken by catalogue order)."""
    order = list(ATTRIBUTES_BY_ID)
    ranked = sorted(
        (a for a, v in weights.items() if v > 0),
        key=lambda a: (-weights[a], order.index(a)),
    )
    return [ATTRIBUTES_BY_ID[a].label for a in ranked[:n]]


def _join(labels: list[str]) -> str:
    labels = [label.lower() for label in labels]
    if len(labels) <= 1:
        return "".join(labels)
    return ", ".join(labels[:-1]) + " and " + labels[-1]


def predict_persona(bundle: ProfileBundle, answers: Answers, weights: dict[str, int]) -> Persona:
    dest = bundle.destination(answers.destination) if answers.destination else None
    kind = dest.kind if dest else None
    pid, title, emoji, tagline = _FALLBACK
    for rule_id, rule_title, rule_emoji, rule_tagline, rule in _RULES:
        if rule(weights, kind):
            pid, title, emoji, tagline = rule_id, rule_title, rule_emoji, rule_tagline
            break
    priorities = top_priorities(weights)
    summary = tagline
    if priorities:
        summary += f" What matters most to you: {_join(priorities)}."
    return Persona(pid, title, emoji, tagline, priorities, summary)
