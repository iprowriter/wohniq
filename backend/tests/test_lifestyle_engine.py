"""Lifestyle Match engine (Step 2): questionnaire, weights, scoring, explanations, persona."""

import re

import pytest
from pydantic import ValidationError

from lifestyle.attributes import ATTRIBUTES
from lifestyle.explain import explain_match
from lifestyle.persona import predict_persona, top_priorities
from lifestyle.profiles import get_bundle
from lifestyle.questionnaire import PRESETS, PRESETS_BY_ID, QUESTIONS, Answers
from lifestyle.scoring import MatchError, limit_score, match
from lifestyle.weights import Weights, apply_overrides, derive_weights

BUNDLE = get_bundle()


def _answers(**kw) -> Answers:
    base = dict(budget_eur=1200, size_m2=50)
    return Answers(**{**base, **kw})


# --- Questionnaire ----------------------------------------------------------------------


def test_answers_reject_unknown_fields():
    """Privacy guard: nothing but the defined, bounded choices can be submitted."""
    with pytest.raises(ValidationError):
        Answers(budget_eur=700, size_m2=30, name="Alex")
    with pytest.raises(ValidationError):
        Answers(budget_eur=700, size_m2=30, evenings="party every night")  # not an option


@pytest.mark.parametrize(
    "kw",
    [
        {"weekends": ("nature", "nature")},  # duplicate
        {"weekends": ("nature", "culture", "active")},  # more than two
        {"budget_eur": 50},
        {"size_m2": 1000},
        {"max_commute_min": 500},
    ],
)
def test_answers_are_bounded(kw):
    with pytest.raises(ValidationError):
        _answers(**kw)


def test_every_option_maps_to_known_attributes_and_levels():
    ids = {a.id for a in ATTRIBUTES}
    for q in QUESTIONS:
        assert q.options, q.id
        for opt in q.options:
            assert set(opt.weights) <= ids, (q.id, opt.id)
            assert all(0 <= v <= 5 for v in opt.weights.values())


def test_no_question_asks_about_protected_characteristics():
    text = " ".join(
        [q.prompt for q in QUESTIONS] + [o.label for q in QUESTIONS for o in q.options]
    ).lower()
    for word in ("age", "gender", "religion", "nationality", "origin", "income", "health"):
        assert not re.search(rf"\b{word}\b", text), word


# --- Presets reproduce the approved weights exactly --------------------------------------

APPROVED = {
    "student": {
        "commute": 5,
        "affordability": 5,
        "young_crowd": 4,
        "transit": 4,
        "nightlife": 3,
        "cafes": 3,
    },
    # Destination is picked by the user; commute 4 then applies.
    "young_professional": {
        "cafes": 4,
        "transit": 4,
        "nightlife": 3,
        "culture": 3,
        "safety": 3,
        "affordability": 1,
    },
    "family": {
        "family": 5,
        "green": 5,
        "safety": 5,
        "quiet": 4,
        "everyday": 4,
        "affordability": 1,
    },
    "remote_creative": {"cafes": 5, "culture": 4, "young_crowd": 3, "green": 3, "affordability": 1},
    "calm_green": {"quiet": 5, "green": 5, "water": 4, "safety": 4, "affordability": 1},
}


@pytest.mark.parametrize("preset_id", list(APPROVED))
def test_presets_reproduce_approved_weights(preset_id):
    assert derive_weights(PRESETS_BY_ID[preset_id].answers).active() == APPROVED[preset_id]


def test_presets_use_known_destinations_and_valid_answers():
    ids = {d.id for d in BUNDLE.destinations}
    for p in PRESETS:
        assert p.answers.destination in ids | {None}
    assert PRESETS_BY_ID["student"].answers.size_m2 == 30  # decision: Option A


def test_young_professional_commute_applies_once_a_destination_is_picked():
    a = PRESETS_BY_ID["young_professional"].answers.model_copy(
        update={"destination": "potsdamer_platz"}
    )
    assert derive_weights(a).value("commute") == 4


# --- Weights ----------------------------------------------------------------------------


def test_weights_take_the_highest_level_and_explain_it():
    a = _answers(weekends=("park_cafe", "brunch"), work_style="hybrid")
    w = derive_weights(a)
    assert w.value("cafes") == 4  # max(3, 4, 3), not a sum
    assert w.items["cafes"].reasons == (
        "Your ideal weekend? (pick up to two) → Brunch spots and exploring the Kiez",
    )
    assert w.value("green") == 3


def test_weights_are_independent_of_answer_order():
    a = derive_weights(_answers(weekends=("nature", "brunch")))
    b = derive_weights(_answers(weekends=("brunch", "nature")))
    assert a.as_dict() == b.as_dict()


def test_frequency_needs_a_destination():
    assert derive_weights(_answers(frequency="daily")).value("commute") == 0
    assert (
        derive_weights(_answers(frequency="daily", destination="hu_berlin")).value("commute") == 5
    )


def test_overrides():
    w = apply_overrides(
        derive_weights(_answers(evenings="out_often")), {"nightlife": 1, "water": 5}
    )
    assert w.value("nightlife") == 1 and w.items["nightlife"].overridden
    assert w.value("water") == 5
    with pytest.raises(ValueError):
        apply_overrides(w, {"vibes": 3})
    with pytest.raises(ValueError):
        apply_overrides(w, {"water": 9})


# --- Scoring ----------------------------------------------------------------------------


def test_limit_score_shape():
    assert limit_score(50, 70, 100, 130) == 1.0
    assert limit_score(70, 70, 100, 130) == 1.0
    assert limit_score(100, 70, 100, 130) == 0.5
    assert limit_score(115, 70, 100, 130) == pytest.approx(0.25)
    assert limit_score(200, 70, 100, 130) == 0.0


def _student():
    a = PRESETS_BY_ID["student"].answers
    return a, derive_weights(a)


def test_matching_is_deterministic():
    a, w = _student()
    first = [(m.region.key, m.total) for m in match(BUNDLE, a, w).results]
    second = [(m.region.key, m.total) for m in match(BUNDLE, a, w).results]
    assert first == second
    assert len(first) == 143


def test_over_budget_regions_are_shown_but_ranked_after_affordable_ones():
    a, w = _student()
    results = match(BUNDLE, a, w).results
    fits = [m.fits_budget for m in results]
    assert any(fits) and not all(fits)  # both kinds present…
    assert fits == sorted(fits, reverse=True)  # …and every affordable one comes first
    over = next(m for m in results if not m.fits_budget)
    assert over.warm_rent_eur > a.budget_eur


def test_excluding_a_region_changes_nothing_else():
    a, w = _student()
    full = {m.region.key: m.total for m in match(BUNDLE, a, w).results}
    top = next(iter(full))
    partial = match(BUNDLE, a, w, excluded=[top])
    assert top not in {m.region.key for m in partial.results}
    assert all(full[m.region.key] == m.total for m in partial.results)
    assert partial.results[0].rank == 1 and partial.excluded == [top]


@pytest.mark.parametrize("attribute", ["cafes", "green", "safety", "quiet", "transit"])
def test_raising_a_weight_never_hurts_the_best_region_for_it(attribute):
    a = _answers()
    base = {"nightlife": 3, "water": 3, "family": 2, attribute: 0}
    best = max(BUNDLE.regions, key=lambda r: BUNDLE.score(attribute, r.measures[attribute].raw))
    ranks = []
    for level in range(6):
        w = apply_overrides(Weights(), {**base, attribute: level})
        ranks.append(next(m.rank for m in match(BUNDLE, a, w).results if m.region == best))
    assert ranks == sorted(ranks, reverse=True)  # rank number never goes up


def test_errors_are_reported_not_guessed():
    a, w = _student()
    with pytest.raises(MatchError, match="destination"):
        match(BUNDLE, a.model_copy(update={"destination": "mars"}), w)
    with pytest.raises(MatchError, match="region"):
        match(BUNDLE, a, w, excluded=["999999"])
    with pytest.raises(MatchError, match="at least one"):
        match(BUNDLE, a, Weights())


def test_commute_without_destination_is_reported_unscored():
    a = _answers()
    w = apply_overrides(Weights(), {"commute": 5, "cafes": 3})
    result = match(BUNDLE, a, w)
    assert "commute" in result.unscored
    assert all(f.attribute != "commute" for m in result.results for f in m.factors)


def test_beyond_max_commute_is_ranked_lower():
    a = _answers(destination="tu_berlin", frequency="daily", max_commute_min=20)
    w = derive_weights(a)
    results = match(BUNDLE, a, w).results
    within = [m.within_commute for m in results if m.fits_budget]
    assert within == sorted(within, reverse=True)


# --- Explanations -----------------------------------------------------------------------


def test_every_reason_carries_a_number_and_a_real_source():
    for preset in PRESETS:
        a = preset.answers
        if a.destination is None and preset.id == "young_professional":
            a = a.model_copy(update={"destination": "alexanderplatz"})
        for m in match(BUNDLE, a, derive_weights(a), limit=10).results:
            e = explain_match(m, BUNDLE, a)
            assert e.headline
            for ev in e.evidence:
                assert re.search(r"\d", ev.text), ev.text
                assert ev.source_id in BUNDLE.sources


def test_over_budget_and_weak_spots_are_stated_honestly():
    a, w = _student()
    results = match(BUNDLE, a, w).results
    over = next(m for m in results if not m.fits_budget)
    e = explain_match(over, BUNDLE, a)
    assert any("over your budget" in c for c in e.caveats)
    # Data caveats are notes, not trade-offs of the area.
    assert any("district median" in n for n in e.notes)
    assert not any("district median" in c for c in e.caveats)


def test_busy_centre_crime_note_only_when_safety_matters():
    a = _answers(safety="top", evenings="out_often")
    w = derive_weights(a)
    by_name = {m.region.name: m for m in match(BUNDLE, a, w).results}
    alex = explain_match(by_name["Alexanderplatz"], BUNDLE, a)
    assert any("visitors" in n for n in alex.notes)
    quiet = _answers(evenings="out_often")
    alex2 = match(BUNDLE, quiet, derive_weights(quiet)).results
    alex2 = next(m for m in alex2 if m.region.name == "Alexanderplatz")
    assert not any("visitors" in n for n in explain_match(alex2, BUNDLE, quiet).notes)


def test_student_top_match_explanation_mentions_tu_berlin_minutes():
    a, w = _student()
    top = match(BUNDLE, a, w, limit=3).results
    texts = [ev.text for m in top for ev in explain_match(m, BUNDLE, a).evidence]
    assert any(re.search(r"≈ \d+ min to TU Berlin", t) for t in texts)


# --- Persona ----------------------------------------------------------------------------

EXPECTED_PERSONA = {
    "student": "campus_explorer",
    "family": "nest_builder",
    "calm_green": "green_retreater",
    "remote_creative": "kiez_creative",
}


@pytest.mark.parametrize("preset_id, persona_id", list(EXPECTED_PERSONA.items()))
def test_persona_for_presets(preset_id, persona_id):
    a = PRESETS_BY_ID[preset_id].answers
    persona = predict_persona(BUNDLE, a, derive_weights(a).active())
    assert persona.id == persona_id
    assert persona.priorities and persona.disclaimer


def test_young_professional_with_a_destination_is_a_go_getter():
    a = PRESETS_BY_ID["young_professional"].answers.model_copy(
        update={"destination": "potsdamer_platz"}
    )
    assert predict_persona(BUNDLE, a, derive_weights(a).active()).id == "urban_go_getter"


def test_persona_fallback_and_priorities():
    a = _answers()
    persona = predict_persona(BUNDLE, a, {"safety": 2})
    assert persona.id == "berlin_balancer"
    assert top_priorities({"water": 4, "cafes": 4, "quiet": 5}) == [
        "Quiet",
        "Cafés & food",
        "Water & nature",
    ]


def test_persona_copy_is_respectful():
    from lifestyle import persona as module

    copy = " ".join(t for _, t, _, tag, _ in module._RULES for t in (t, tag)).lower()
    for word in ("young people", "old", "rich", "poor", "foreign", "age", "gender"):
        assert not re.search(rf"\b{word}\b", copy), word
