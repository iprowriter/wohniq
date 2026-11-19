"""Berlin area gazetteer + mention extraction (pure, no network).

Regression suite for the "districts are ignored" bug: "a quiet flat in Mitte, Spandau,
Lichtenberg, Treptow" used to parse to just quiet=True.
"""

import pytest

from search.areas import (
    AREAS,
    BY_NAME,
    DISTRICT,
    area_sql_terms,
    canonical_areas,
    find_area_mentions,
    listing_in_area,
    matching_area,
    nearest_area,
    resolve_area,
)


def _want(text):
    return find_area_mentions(text).want


def test_the_reported_query_keeps_every_district():
    assert _want("a quiet flat in Mitte, Spandau, Lichtenberg, Treptow") == [
        "Mitte",
        "Spandau",
        "Lichtenberg",
        "Treptow",
    ]


@pytest.mark.parametrize(
    "typed, canonical",
    [
        ("Prenzlauerberg", "Prenzlauer Berg"),
        ("prenzlauer berg", "Prenzlauer Berg"),
        ("P'berg", "Prenzlauer Berg"),
        ("P-Berg", "Prenzlauer Berg"),
        ("Pberg", "Prenzlauer Berg"),
        ("Prenzlberg", "Prenzlauer Berg"),
        ("Kollwitzkiez", "Prenzlauer Berg"),
        ("Xberg", "Kreuzberg"),
        ("X-Berg", "Kreuzberg"),
        ("SO36", "Kreuzberg"),
        ("Graefekiez", "Kreuzberg"),
        ("Fhain", "Friedrichshain"),
        ("F'hain", "Friedrichshain"),
        ("Neukoelln", "Neukölln"),
        ("Neukolln", "Neukölln"),
        ("Nkln", "Neukölln"),
        ("Reuterkiez", "Neukölln"),
        ("Kreuzkölln", "Kreuzkölln"),
        ("Schoeneberg", "Schöneberg"),
        ("Weissensee", "Weißensee"),
        ("Berlin-Mitte", "Mitte"),
        ("Alt-Treptow", "Treptow"),
        ("Koepenick", "Köpenick"),
        ("Friedrichshain-Kreuzberg", "Friedrichshain-Kreuzberg"),
        ("Xhain", "Friedrichshain-Kreuzberg"),
        ("Bezirk Mitte", "Bezirk Mitte"),
        ("Kreutzberg", "Kreuzberg"),  # typo
        ("Lichtenburg", "Lichtenberg"),  # typo
    ],
)
def test_names_nicknames_and_spellings_resolve(typed, canonical):
    assert resolve_area(typed).name == canonical
    assert _want(f"a flat in {typed}") == [canonical]


def test_unknown_places_are_not_areas():
    assert resolve_area("Alexanderplatz") is None
    assert resolve_area("Narnia") is None
    assert canonical_areas(["Mitte", "Narnia", "mitte", "P'berg"]) == ["Mitte", "Prenzlauer Berg"]


def test_bare_names_mean_the_ortsteil_and_compound_names_the_district():
    assert resolve_area("Mitte").kind != DISTRICT  # "Mitte" = central Mitte, not Wedding
    assert resolve_area("Pankow").kind != DISTRICT  # not all of Bezirk Pankow (P'berg)
    assert resolve_area("Treptow-Köpenick").kind == DISTRICT
    assert resolve_area("Mitte district").name == "Bezirk Mitte"


def test_avoided_areas_are_not_wanted():
    found = find_area_mentions("anywhere but Neukölln or Marzahn")
    assert found.want == [] and found.avoid == ["Neukölln", "Marzahn"]
    found = find_area_mentions("flat in Mitte but not Wedding")
    assert found.want == ["Mitte"] and found.avoid == ["Wedding"]
    found = find_area_mentions("I don't want to live in Neukölln, prefer Schöneberg")
    assert found.want == ["Schöneberg"] and found.avoid == ["Neukölln"]


def test_negation_must_be_next_to_the_place():
    assert _want("quiet place, not too loud in Mitte") == ["Mitte"]
    assert _want("flat with no balcony in Mitte") == ["Mitte"]
    assert _want("something cheap but in Mitte") == ["Mitte"]


def test_workplace_is_not_a_living_area():
    found = find_area_mentions("I work in Mitte and want a quiet flat in Pankow")
    assert found.want == ["Pankow"] and found.work == ["Mitte"]
    found = find_area_mentions("my office is in Kreuzberg, flat in Pankow")
    assert found.want == ["Pankow"] and found.work == ["Kreuzberg"]
    # "work" far from the place name doesn't make it a workplace
    assert _want("I work from home and want a flat in Mitte") == ["Mitte"]


@pytest.mark.parametrize(
    "text, area",
    [
        ("I am a student in Charlottenburg, looking for a room", "Charlottenburg"),
        ("I'm a student at TU in Charlottenburg", "Charlottenburg"),
        ("I teach at a school in Neukölln, flat nearby", "Neukölln"),
        ("I'm a teacher in Neukölln", "Neukölln"),
        ("doing an internship in Mitte, 1 room", "Mitte"),
        ("internship at Zalando in Friedrichshain", "Friedrichshain"),
        ("starting an apprenticeship in Spandau", "Spandau"),
        ("my Ausbildung is in Lichtenberg", "Lichtenberg"),
        ("doing my PhD at FU in Dahlem", "Dahlem"),
        ("I'm a lecturer in Mitte", "Mitte"),
        # already understood before the wording was extended (must not regress)
        ("I study in Charlottenburg", "Charlottenburg"),
        ("my job is in Mitte", "Mitte"),
        ("good commute to Mitte", "Mitte"),
    ],
)
def test_study_teaching_and_training_places_are_workplaces(text, area):
    found = find_area_mentions(text)
    assert found.work == [area] and found.want == []


@pytest.mark.parametrize(
    "text, area",
    [
        # "school" alone is not a workplace word: families choose where to live by schools
        ("3 rooms for a family near a good school in Pankow", "Pankow"),
        ("close to schools, in Pankow", "Pankow"),
        # "student" describing the flat, not the person's place of study
        ("looking for a student room in Mitte", "Mitte"),
        ("student flat near Kreuzberg", "Kreuzberg"),
        ("as a student I want a cheap flat in Wedding", "Wedding"),
        ("I can attend viewings in Mitte anytime", "Mitte"),
    ],
)
def test_school_and_student_wording_that_describes_the_home_stays_a_wish(text, area):
    found = find_area_mentions(text)
    assert found.want == [area] and found.work == []


def test_english_word_wedding_needs_a_place_context():
    assert _want("need a flat after our wedding, 2 rooms") == []
    assert _want("a flat in wedding please") == ["Wedding"]
    assert _want("Wedding or Moabit") == ["Wedding", "Moabit"]


def test_listing_matching_by_kiez_and_district():
    mitte, bezirk_mitte = BY_NAME["Mitte"], BY_NAME["Bezirk Mitte"]
    assert listing_in_area("Mitte", "Mitte", mitte)
    assert not listing_in_area("Moabit", "Mitte", mitte)  # Ortsteil only
    assert listing_in_area("Moabit", "Mitte", bezirk_mitte)  # whole district
    kreuzkoelln = BY_NAME["Kreuzkölln"]
    assert listing_in_area("Neukölln", "Neukölln", kreuzkoelln)
    assert listing_in_area("Kreuzberg", "Friedrichshain-Kreuzberg", kreuzkoelln)
    assert matching_area("Treptow", "Treptow-Köpenick", ["Mitte", "Treptow"]) == "Treptow"
    assert matching_area("Neukölln", "Neukölln", ["Mitte", "Treptow"]) is None


def test_sql_terms_cover_kieze_and_districts():
    kieze, districts = area_sql_terms(["Mitte", "Kreuzkölln", "Treptow-Köpenick"])
    assert kieze == ["Mitte", "Neukölln", "Kreuzberg"]
    assert districts == ["Treptow-Köpenick"]


def test_nearest_area_distance_is_plausible():
    # A Moabit flat is a few km from central Mitte, and much further from Spandau.
    name, km = nearest_area(52.530, 13.342, ["Mitte", "Spandau"])
    assert name == "Mitte" and 3 < km < 6


def test_gazetteer_is_consistent():
    names = [a.name for a in AREAS]
    assert len(names) == len(set(names))  # canonical names are unique
    for area in AREAS:
        assert 52.3 < area.lat < 52.7 and 13.05 < area.lng < 13.8, area.name
        assert resolve_area(area.name) is area
    # Every listing Kiez used by the synthetic data is reachable.
    from data.kieze import KIEZE

    for kiez in KIEZE:
        assert resolve_area(kiez.name) is not None, kiez.name
        assert matching_area(kiez.name, kiez.district, [resolve_area(kiez.name).name])
