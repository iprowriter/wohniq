"""Berlin Neighbourhoods — bundle validation, scoring, ranking and explanations."""

import pytest

from neighborhoods.bundle import NeighbourhoodBundle, get_bundle
from neighborhoods.catalog import CATEGORIES, CATEGORIES_BY_ID, METRICS, METRICS_BY_ID
from neighborhoods.explain import format_value, headline_metric, highlights, summary
from neighborhoods.scoring import (
    RankingError,
    category_table,
    percentile,
    rank_areas,
    ranks_by_category,
    tier_for,
    validate_weights,
)

SOURCE = {
    "id": "src",
    "title": "T",
    "publisher": "P",
    "data_year": "2025",
    "used_for": "u",
}


def _value(raw):
    return {"raw": raw, "source_id": "src", "year": "2025", "method": "m"}


def _bundle(values: dict[str, dict[str, float]]) -> NeighbourhoodBundle:
    """A tiny bundle: area key -> metric id -> raw value."""
    metrics = sorted({m for v in values.values() for m in v})
    regions = [
        {
            "key": key,
            "name": f"Area {key}",
            "district": "Mitte",
            "area_group": "Zentrum",
            "population": 1000,
            "centroid": [52.5, 13.4],
            "area_km2": 1.0,
            "values": {m: _value(v[m]) for m in metrics},
        }
        for key, v in values.items()
    ]
    refs = {
        m: {
            "berlin": 1.0,
            "berlin_method": "x",
            "distribution": sorted(v[m] for v in values.values()),
        }
        for m in metrics
    }
    return NeighbourhoodBundle.model_validate(
        {"schema_version": 1, "sources": {"src": SOURCE}, "references": refs, "regions": regions}
    )


# --- Percentiles -----------------------------------------------------------------------------


def test_percentile_best_worst_and_middle():
    d = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(d, 5.0, higher_is_better=True) == 1.0
    assert percentile(d, 1.0, higher_is_better=True) == 0.0
    assert percentile(d, 3.0, higher_is_better=True) == 0.5
    assert percentile(d, 1.0, higher_is_better=False) == 1.0  # lowest crime = best


def test_percentile_ties_count_half_and_all_equal_is_middle():
    assert percentile([1.0, 2.0, 2.0, 3.0], 2.0, True) == pytest.approx((1 + 0.5) / 3)
    assert percentile([7.0, 7.0, 7.0], 7.0, False) == 0.5


def test_percentile_outside_the_distribution_is_clipped():
    assert percentile([1.0, 2.0], 10.0, True) == 1.0
    assert percentile([1.0, 2.0], -1.0, True) == 0.0


def test_outliers_do_not_squash_other_scores():
    # Unlike min–max scaling, one extreme value leaves the others evenly spread.
    d = sorted([100.0, 110.0, 120.0, 130.0, 100_000.0])
    scores = [percentile(d, v, False) for v in (100.0, 110.0, 120.0, 130.0)]
    assert scores == [1.0, 0.75, 0.5, 0.25]


# --- Categories and ranking ------------------------------------------------------------------


def test_category_score_is_weighted_and_ignores_zero_weight_metrics():
    # crime_kiez (w3) best in A, crime_total (w1) worst in A; nightlife weight 0 doesn't count.
    b = _bundle(
        {
            "011001": {"crime_kiez": 1, "crime_total": 9, "nightlife": 0},
            "011002": {"crime_kiez": 9, "crime_total": 1, "nightlife": 50},
        }
    )
    t = category_table(b)
    assert t["011001"]["safety"].score == pytest.approx(75.0)  # (3·100 + 1·0) / 4
    assert t["011002"]["safety"].score == pytest.approx(25.0)
    assert t["011001"]["amenities"].score is None  # only a context metric


def test_rank_areas_shares_ranks_on_ties_and_orders_by_name():
    b = _bundle({"011003": {"rent": 10}, "011001": {"rent": 10}, "011002": {"rent": 20}})
    ranked = rank_areas(b, "affordability")
    assert [(r.area.key, r.rank) for r in ranked] == [("011001", 1), ("011003", 1), ("011002", 3)]


def test_rank_unknown_category_or_missing_data_is_an_error():
    b = _bundle({"011001": {"rent": 10}, "011002": {"rent": 20}})
    with pytest.raises(RankingError, match="unknown"):
        rank_areas(b, "vibes")
    with pytest.raises(RankingError, match="no data"):
        rank_areas(b, "safety")
    with pytest.raises(RankingError, match="overall"):
        rank_areas(b, "affordability", weights={"safety": 1})


def test_overall_weights_change_the_order():
    b = _bundle(
        {
            "011001": {"crime_kiez": 1, "rent": 30},  # safe, expensive
            "011002": {"crime_kiez": 9, "rent": 10},  # less safe, cheap
        }
    )
    safety_first = rank_areas(b, "overall", {"safety": 3, "affordability": 1})
    money_first = rank_areas(b, "overall", {"safety": 1, "affordability": 3})
    assert safety_first[0].area.key == "011001"
    assert money_first[0].area.key == "011002"


def test_validate_weights():
    assert validate_weights(None)["safety"] == CATEGORIES_BY_ID["safety"].default_weight
    assert validate_weights({"parking": 0})["parking"] == 0
    with pytest.raises(RankingError):
        validate_weights({"safety": 4})
    with pytest.raises(RankingError):
        validate_weights({"nope": 1})
    with pytest.raises(RankingError, match="at least one"):
        validate_weights({c.id: 0 for c in CATEGORIES})


def test_tiers_are_top_and_bottom_twenty_percent():
    n = 143  # cut = 29
    assert tier_for(1, n) == "best" and tier_for(29, n) == "best"
    assert tier_for(30, n) == "middle" and tier_for(114, n) == "middle"
    assert tier_for(115, n) == "worst" and tier_for(143, n) == "worst"


# --- Bundle validation ------------------------------------------------------------------------


def test_bundle_rejects_unknown_metric_source_and_gaps():
    good = _bundle({"011001": {"rent": 1}, "011002": {"rent": 2}}).model_dump()
    bad = {**good, "references": {**good["references"], "vibes": good["references"]["rent"]}}
    with pytest.raises(ValueError, match="unknown metric"):
        NeighbourhoodBundle.model_validate(bad)
    bad = {**good, "sources": {}}
    with pytest.raises(ValueError, match="unknown source"):
        NeighbourhoodBundle.model_validate(bad)
    short = {**good["references"]["rent"], "distribution": [1.0, 2.0, 3.0]}
    with pytest.raises(ValueError, match="covers"):
        NeighbourhoodBundle.model_validate({**good, "references": {"rent": short}})
    pending = {**good["references"], "income": good["references"]["rent"]}  # still pending
    with pytest.raises(ValueError, match="pending"):
        NeighbourhoodBundle.model_validate({**good, "references": pending})


# --- The shipped bundle ---------------------------------------------------------------------------


def test_shipped_bundle_covers_all_areas_and_every_available_metric():
    b = get_bundle()
    assert len(b.regions) == 143
    available = {m.id for m in b.available()}
    assert available == {m.id for m in METRICS if not m.requires}
    assert {m.id for m in b.pending()} == {"income"}
    for r in b.regions:
        assert set(r.values) == available


def test_every_category_has_a_score_for_every_area():
    t = category_table(get_bundle())
    for key, scores in t.items():
        for c in CATEGORIES:
            assert scores[c.id].score is not None, (key, c.id)
            assert 0 <= scores[c.id].score <= 100


def test_catalog_weights_and_labels_are_sane():
    for c in CATEGORIES:
        assert 0 <= c.default_weight <= 3 and c.best_label and c.worst_label and c.caveat
        assert "avoid" not in (c.best_label + c.worst_label + c.caveat).lower()
        assert headline_metric(c).category == c.id
    for m in METRICS:
        assert m.category in CATEGORIES_BY_ID and m.weight >= 0


# --- Explanations ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "metric,raw,text",
    [
        ("crime_kiez", 3198.14, "3,198"),
        ("accidents", 4.567, "4.6"),
        ("social_status", 1.8734, "1.87"),
        ("edu_abitur", 44.04, "44.0%"),
        ("hospital_distance", 394.0, "390 m"),
        ("hospital_distance", 5475.0, "5.5 km"),
        ("commute_centre", 23.0, "23 min"),
        ("rent", 15.78, "€15.78/m²"),
    ],
)
def test_format_value(metric, raw, text):
    assert format_value(METRICS_BY_ID[metric], raw) == text


def test_highlights_quote_the_stored_number_and_rank():
    b = get_bundle()
    ranks = ranks_by_category(b)
    key = next(a.key for a in b.regions if a.name == "Müggelheim")
    strengths, watch = highlights(b, key)
    assert strengths and watch
    by_cat = {h.category: h for h in strengths}
    assert "safety" in by_cat
    h = by_cat["safety"]
    raw = b.area(key).values["crime_kiez"].raw
    assert format_value(METRICS_BY_ID["crime_kiez"], raw) in h.text
    assert f"#{ranks['safety'][key].rank} of 143" in h.text
    assert h.source_id == "pks_kriminalitaetsatlas"
    assert all(w.rank > 114 for w in watch)


def test_summary_names_the_strongest_and_weakest_category():
    b = get_bundle()
    key = b.regions[0].key
    text = summary(b, key, overall_rank=7)
    assert text.startswith("#7 of 143 overall.") and "Strongest:" in text and "weakest:" in text
