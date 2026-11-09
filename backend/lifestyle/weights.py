"""Answers → weights (deterministic, explainable; ADR-0011).

Each chosen option sets importance levels (0–5) for some attributes; an attribute's
weight is the **highest** level any chosen option gives it. Max (not sum) keeps weights
on the 0–5 scale, makes the result independent of answer order, and means every weight
can be explained by one or more concrete answers.

Users can then override any weight directly (the results page sliders); overrides
replace the derived value and are reported as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lifestyle.attributes import ATTRIBUTES, ATTRIBUTES_BY_ID
from lifestyle.questionnaire import Answers

MAX_WEIGHT = 5


@dataclass(frozen=True)
class Weight:
    attribute: str
    value: int  # 0..5
    reasons: tuple[str, ...] = ()  # the answers that set it ("How often … → Every day")
    overridden: bool = False  # set directly by the user


@dataclass(frozen=True)
class Weights:
    items: dict[str, Weight] = field(default_factory=dict)

    def value(self, attribute: str) -> int:
        w = self.items.get(attribute)
        return w.value if w else 0

    def as_dict(self) -> dict[str, int]:
        return {a: w.value for a, w in self.items.items()}

    def active(self) -> dict[str, int]:
        return {a: w.value for a, w in self.items.items() if w.value > 0}


def derive_weights(answers: Answers) -> Weights:
    """Weights from answers: per attribute, the highest level any chosen option sets."""
    levels: dict[str, int] = {a.id: 0 for a in ATTRIBUTES}
    reasons: dict[str, list[str]] = {a.id: [] for a in ATTRIBUTES}
    for question, option in answers.chosen():
        for attribute, level in option.weights.items():
            if question.id == "frequency" and not answers.destination:
                continue  # commute frequency only matters once a destination is picked
            reason = f"{question.prompt} → {option.label}"
            if level > levels[attribute]:
                levels[attribute] = level
                reasons[attribute] = [reason]
            elif level == levels[attribute] and level > 0:
                reasons[attribute].append(reason)
    return Weights({a: Weight(a, levels[a], tuple(reasons[a])) for a in levels})


def apply_overrides(weights: Weights, overrides: dict[str, int] | None) -> Weights:
    """Replace derived weights with the user's own (validated: known ids, 0..5)."""
    if not overrides:
        return weights
    items = dict(weights.items)
    for attribute, value in overrides.items():
        if attribute not in ATTRIBUTES_BY_ID:
            raise ValueError(f"Unknown attribute {attribute!r}")
        if not isinstance(value, int) or not 0 <= value <= MAX_WEIGHT:
            raise ValueError(f"Weight for {attribute!r} must be an integer 0–{MAX_WEIGHT}")
        previous = items.get(attribute)
        if previous is None or previous.value != value:
            items[attribute] = Weight(attribute, value, ("Set by you",), overridden=True)
    return Weights(items)
