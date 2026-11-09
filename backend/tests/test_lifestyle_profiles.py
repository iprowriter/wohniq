"""Lifestyle Match data model (Step 1): the shipped bundle, normalisation, validation."""

import json

import pytest
from pydantic import ValidationError

from data.kieze import KIEZE
from lifestyle.attributes import ATTRIBUTES, get_attribute
from lifestyle.profiles import BUNDLE_PATH, ProfileBundle, get_bundle

# --- The shipped bundle ---------------------------------------------------------------


def test_bundle_covers_all_of_berlin():
    bundle = get_bundle()
    assert len(bundle.regions) == 143  # every LOR Bezirksregion
    assert len({r.district for r in bundle.regions}) == 12  # every Bezirk
    # Register total for 31.12.2024 (SB A I 16 – hj 2/24): nobody dropped or double-counted.
    assert sum(r.population for r in bundle.regions) == 3_897_145


CLASS_BASED = ("quiet", "green", "clean_air", "cool_summer")
COUNTS = ("cafes", "everyday", "nightlife", "culture", "sport")  # log-scaled
DISTANCES = ("water", "transit")  # metres, lower is better
ALL_AREA = ("safety", "family", "young_crowd", *CLASS_BASED, *COUNTS, *DISTANCES)


def test_every_measure_is_sourced_and_sane():
    bundle = get_bundle()
    for region in bundle.regions:
        assert set(region.measures) == set(ALL_AREA)
        for attr_id, m in region.measures.items():
            assert m.source_id in bundle.sources
            assert m.unit and m.year and m.method
            if attr_id in ("family", "young_crowd"):
                assert 0 < m.raw < 100  # a percentage
            elif attr_id in CLASS_BASED:
                assert 1 <= m.raw <= 3
                assert set(m.shares) == {"best", "middle", "worst"}
                assert sum(m.shares.values()) == pytest.approx(100, abs=0.2)
            elif attr_id in COUNTS:
                assert m.raw >= 0
            elif attr_id in DISTANCES:
                assert 0 <= m.raw <= 3000  # capped at 3 km
            else:
                assert m.raw > 0


def test_references_are_fixed_ranges():
    bundle = get_bundle()
    for attr_id, ref in bundle.references.items():
        raws = sorted(r.measures[attr_id].raw for r in bundle.regions)
        assert ref.scale == ("log" if attr_id in COUNTS else "linear")
        if attr_id in CLASS_BASED:
            assert (ref.low, ref.high) == (1.0, 3.0)  # class bounds, not data-dependent
        else:
            assert raws[0] <= ref.low < ref.high <= raws[-1]  # 10th–90th percentile
        assert raws[0] <= ref.berlin <= raws[-1]
        assert ref.method


def test_geography_matches_official_figures():
    bundle = get_bundle()
    # Sum of published Planungsraum areas = Berlin's 891 km².
    assert sum(r.area_km2 for r in bundle.regions) == pytest.approx(891.1, abs=0.5)
    by_name = {r.name: r for r in bundle.regions}
    # Police foreword (Kriminalitätsatlas): Helmholtzplatz is Berlin's smallest and densest
    # region — 0.71 km², ~32,000 residents/km² (mid-2025).
    helmholtz = by_name["Helmholtzplatz"]
    assert helmholtz.area_km2 == pytest.approx(0.71, abs=0.01)
    assert helmholtz.density_per_km2 == pytest.approx(32_055, rel=0.02)
    assert helmholtz.density_per_km2 == max(r.density_per_km2 for r in bundle.regions)
    assert by_name["Zehlendorf Südwest"].area_km2 == pytest.approx(43.3, rel=0.01)
    for r in bundle.regions:
        lat, lng = r.centroid
        assert 52.33 < lat < 52.68 and 13.08 < lng < 13.77  # inside Berlin


def test_rent_is_the_official_district_median():
    bundle = get_bundle()
    # IBB Tabellenband 2025, Tab. 25 — spot-check three districts.
    expected = {"Mitte": 20.00, "Charlottenburg-Wilmersdorf": 19.17, "Marzahn-Hellersdorf": 11.56}
    for r in bundle.regions:
        assert r.rent.source_id == "ibb_tabellenband_2025"
        assert 10 < r.rent.raw < 21
        if r.district in expected:
            assert r.rent.raw == expected[r.district]
        assert "80% of offers" in r.rent.method
    by_name = {r.name: r for r in bundle.regions}
    assert by_name["Helmholtzplatz"].inner_city_share == 1.0  # inside the S-Bahn ring
    assert by_name["Karow"].inner_city_share == 0.0


def test_district_rents_are_consistent_with_the_berlin_median():
    from data.lifestyle.sources import DISTRICT_RENTS

    assert len(DISTRICT_RENTS) == 12
    medians = sorted(m for m, _, _ in DISTRICT_RENTS.values())
    berlin = get_bundle().city["asking_rent_median"].value  # 15.78
    assert medians[0] < berlin < medians[-1]
    assert all(low < median < high for median, low, high in DISTRICT_RENTS.values())


def test_commute_matrix_covers_every_destination_and_region():
    bundle = get_bundle()
    assert len(bundle.destinations) == 13
    assert bundle.commute.source_id in bundle.sources
    for dest in bundle.destinations:
        times = bundle.commute.times[dest.id]
        assert len(times) == 143
        assert all(0 < t.minutes < 150 for t in times.values())
        network = sum(t.source == "network" for t in times.values())
        assert network / len(times) > 0.9  # timetable routes, not straight-line guesses
    by_name = {r.name: r for r in bundle.regions}
    # TU Berlin's campus lies in Otto-Suhr-Allee/Kantstraße: a short trip from there…
    assert bundle.commute_time("tu_berlin", by_name["Otto-Suhr-Allee/Kantstraße"].key).minutes <= 20
    # …and a long one from the far south-east.
    assert bundle.commute_time("tu_berlin", by_name["Müggelheim"].key).minutes >= 50


def test_rent_range_is_the_district_spread():
    for r in get_bundle().regions:
        low, high = r.rent_range
        assert low < r.rent.raw < high


def test_listing_kieze_map_to_real_kieze_and_cover_all_of_them():
    bundle = get_bundle()
    mapped = {r.listing_kiez for r in bundle.regions if r.listing_kiez}
    assert mapped == {k.name for k in KIEZE}


def test_region_names_are_clean_and_unique():
    names = [r.name for r in get_bundle().regions]
    assert len(names) == len(set(names))  # e.g. the two "Heerstraße"s are disambiguated
    assert all("  " not in n and n == n.strip() for n in names)


def test_city_figures_are_plausible_and_sourced():
    city = get_bundle().city
    assert 10 < city["asking_rent_median"].value < 25
    assert (
        city["asking_rent_outer_city"].value
        < city["asking_rent_median"].value
        < city["asking_rent_inner_city"].value
    )
    assert city["operating_costs_cold"].value + city["operating_costs_warm"].value == pytest.approx(
        3.43
    )


def test_no_nationality_or_migration_attributes():
    """Privacy/ethics by design: nothing in the model is derived from nationality."""
    banned = ("auslaend", "ausländ", "foreign", "migration", "nationality", "ethnic")
    banned += ("social", "sozial", "status", "poverty", "sgb")  # UG social index not used
    ids = [a.id for a in ATTRIBUTES] + [m for r in get_bundle().regions for m in r.measures]
    assert not [i for i in ids if any(b in i.lower() for b in banned)]


def test_shipped_file_is_deterministic_json():
    text = BUNDLE_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    assert [r["key"] for r in data["regions"]] == sorted(r["key"] for r in data["regions"])
    assert "generated_at" not in data  # no timestamps -> rebuilds diff cleanly


# --- Availability is derived from data, not declared ---------------------------------


def test_available_and_pending_attributes():
    bundle = get_bundle()
    available = [a.id for a in bundle.available_attributes()]
    assert set(available) == set(ALL_AREA)  # every area attribute now has data
    assert bundle.pending_attributes() == []
    assert "commute" not in available  # personal, computed per request


def test_unknown_attribute_raises():
    with pytest.raises(KeyError):
        get_attribute("vibes")


# --- Normalisation --------------------------------------------------------------------


def test_log_scale_rewards_the_first_few_amenities_most():
    bundle = get_bundle()
    ref = bundle.references["cafes"]
    assert ref.scale == "log"
    mid = (ref.low + ref.high) / 2
    assert bundle.score("cafes", mid) > 0.5  # concave: half the count scores > half
    assert bundle.score("cafes", ref.low) == 0.0 and bundle.score("cafes", ref.high) == 1.0


def test_score_direction_and_clamping():
    bundle = get_bundle()
    ref = bundle.references["safety"]
    assert bundle.score("safety", ref.low) == 1.0  # few offences -> safest
    assert bundle.score("safety", ref.high) == 0.0
    assert bundle.score("safety", ref.low / 2) == 1.0  # clamped
    assert bundle.score("safety", ref.high * 3) == 0.0
    fam = bundle.references["family"]
    assert bundle.score("family", fam.high) == 1.0  # more families -> more family-friendly
    mid = (fam.low + fam.high) / 2
    assert bundle.score("family", mid) == pytest.approx(0.5)


def test_known_regions_order_sensibly():
    bundle = get_bundle()
    by_name = {r.name: r for r in bundle.regions}

    def s(name, attr):
        return bundle.score(attr, by_name[name].measures[attr].raw)

    # A residential Kiez reads safer than the visitor-heavy centre.
    assert s("Helmholtzplatz", "safety") > s("Alexanderplatz", "safety")
    # Wedding Zentrum has one of the youngest populations in Berlin.
    assert s("Wedding Zentrum", "young_crowd") > 0.9
    # Umweltgerechtigkeit: residential streets vs. the traffic hub; forest edge vs. Moabit.
    assert s("Helmholtzplatz", "quiet") > s("Alexanderplatz", "quiet")
    assert s("Zehlendorf Südwest", "green") == 1.0
    assert s("Moabit West", "green") == 0.0
    # OSM / VBB access, measured from homes.
    assert s("Helmholtzplatz", "cafes") > s("Karow", "cafes")
    assert s("Reuterstraße", "nightlife") > s("Zehlendorf Südwest", "nightlife")
    assert s("Grünau", "water") > s("Helmholtzplatz", "water")  # on the Dahme river
    assert s("Helmholtzplatz", "transit") > s("Karow", "transit")


def test_score_is_independent_of_other_regions():
    """Fixed references: dropping regions must not change anyone else's score."""
    bundle = get_bundle()
    region = bundle.regions[0]
    before = bundle.score("safety", region.measures["safety"].raw)
    trimmed = bundle.model_copy(update={"regions": bundle.regions[:1]})
    assert trimmed.score("safety", region.measures["safety"].raw) == before


# --- Validation rejects inconsistent bundles ------------------------------------------


def _raw_bundle() -> dict:
    return json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "mutate, message",
    [
        (
            lambda b: b["regions"][0]["measures"]["safety"].update(source_id="nope"),
            "unknown source",
        ),
        (
            lambda b: b["regions"][0]["measures"].update(
                vibes=b["regions"][0]["measures"]["safety"]
            ),
            "unknown attribute",
        ),
        (lambda b: b["references"].pop("family"), "no reference range"),
        (lambda b: b["regions"].append(dict(b["regions"][0])), "duplicate region key"),
        (lambda b: b["regions"][0].update(key="12"), "string_pattern_mismatch"),
        (lambda b: b["references"]["safety"].update(low=9e9), "must be <"),
        (lambda b: b["city"]["asking_rent_median"].update(source_id="nope"), "unknown source"),
        (lambda b: b.update(schema_version=99), "schema_version"),
        (lambda b: b["regions"][0]["rent"].update(source_id="nope"), "rent cites unknown"),
        (lambda b: b["regions"][0].update(geo_source_id=None), "geography cites unknown"),
        (lambda b: b["commute"]["times"].pop("tu_berlin"), "destination list"),
        (lambda b: b["commute"]["times"]["tu_berlin"].pop("011001"), "cover every region"),
        (lambda b: b["commute"].update(source_id="nope"), "commute cites unknown"),
        (lambda b: b["regions"][0].update(inner_city_share=1.5), "less_than_equal"),
    ],
)
def test_validation_rejects_inconsistent_bundles(mutate, message):
    bundle = _raw_bundle()
    mutate(bundle)
    with pytest.raises(ValidationError, match=message):
        ProfileBundle.model_validate(bundle)
